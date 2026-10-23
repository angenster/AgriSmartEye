"""
生成 CNN 基线指标报告（P0 验收产物）。

输出 `reports/cnn_metrics.md`，内容全部来自可复现的文件：
  - checkpoints/<tag>/metrics.json   训练脚本自测（原始 argmax）
  - 生产权重在门禁评测集上重跑       生产推理路径（含屏蔽与作物一致性）
  - reports/cross_domain_*.json      跨域评测

用法（在 ai-model/ 目录下）：
    python training/make_cnn_metrics.py
    python training/make_cnn_metrics.py --skip-eval   # 不加载模型，只汇总已有指标
"""
import argparse
import glob
import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import torch


def _load_json(path: str) -> Optional[Dict]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _macro_f1(y_true: List[str], y_pred: List[str]) -> float:
    labels = sorted(set(y_true))
    scores = []
    for label in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        scores.append(2 * precision * recall / (precision + recall) if (precision + recall) else 0.0)
    return sum(scores) / len(scores) if scores else 0.0


def _checkpoint_meta(path: str) -> Dict:
    ckpt = torch.load(path, map_location="cpu")
    return {
        "version": ckpt.get("version"),
        "labels_version": ckpt.get("labels_version"),
        "trained_classes": ckpt.get("trained_classes") or [],
        "epoch": ckpt.get("epoch"),
    }


def _collect_versions(checkpoints: Path) -> List[Dict]:
    rows = []
    for metrics_path in sorted(glob.glob(str(checkpoints / "*" / "metrics.json"))):
        tag = Path(metrics_path).parent.name
        m = _load_json(metrics_path)
        if not m or not m.get("test"):
            continue  # LoRA 飞轮候选的 metrics.json 结构不同，单独统计
        rows.append({
            "tag": tag,
            "aug": m.get("aug"),
            "n_train": m.get("n_train"),
            "val_acc": (m.get("val") or {}).get("disease_accuracy"),
            "val_f1": (m.get("val") or {}).get("disease_macro_f1"),
            "test_acc": (m.get("test") or {}).get("disease_accuracy"),
            "test_f1": (m.get("test") or {}).get("disease_macro_f1"),
            "best_epoch": m.get("best_epoch"),
        })
    return rows


def _collect_flywheel(checkpoints: Path) -> List[Dict]:
    rows = []
    for metrics_path in sorted(glob.glob(str(checkpoints / "*" / "metrics.json"))):
        tag = Path(metrics_path).parent.name
        m = _load_json(metrics_path)
        if not m or m.get("test") or not m.get("flywheel_samples"):
            continue
        rows.append({
            "tag": tag,
            "base": m.get("base_version"),
            "flywheel": m.get("flywheel_samples"),
            "replay": m.get("replay_samples"),
            "before": m.get("holdout_before"),
            "after": m.get("holdout_after"),
        })
    return rows


def _pick_cross_domain(reports: Path, version_tag: str) -> Optional[str]:
    """选生产版本对应的跨域报告；同时存在带/不带作物掩码的文件时优先带掩码的。"""
    major = (version_tag or "").split("-")[0]
    candidates = sorted(glob.glob(str(reports / f"cross_domain_{major}*.json")))
    if not candidates:
        return None
    masked = [p for p in candidates if "cropmask" in Path(p).name]
    return (masked or candidates)[-1]


def _evaluate(weights: str, dataset: str, trained: List[str], img_size: int = 224) -> Optional[Dict]:
    """用生产推理路径（InferenceEngine）跑门禁评测集。

    评测集里可能包含生产权重从未训练过的类别（如加入菠萝后的 v1_test）。
    这些样本在推理时被屏蔽、必然判错，因此同时给出全量指标与
    “仅训练类”指标，避免把能力缺口混进同域准确率。
    """
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from inference.inference import InferenceEngine
        from labels import crop_of_label
    except Exception as e:  # noqa: BLE001
        return {"error": f"无法加载推理引擎: {type(e).__name__}: {e}"}

    data = _load_json(dataset)
    if not data:
        return {"error": f"评测集不存在或无法读取: {dataset}"}

    trained_set = set(trained)
    # 训练过的作物 = 至少有一个训练病害属于它。菠萝只有“健康”图（无训练病害），
    # 因此整体排除，否则作物头必然判错、把同域指标压低。
    trained_crops = {crop_of_label(label) for label in trained_set if crop_of_label(label)}

    def evaluable(row) -> bool:
        label = row.get("label") or row.get("disease")
        crop = row.get("crop")
        return label in trained_set and (not crop or crop in trained_crops)

    engine = InferenceEngine(weights, device="cpu")
    y_true, y_pred = [], []
    t_true, t_pred = [], []
    crop_ok = crop_n = 0
    per_label: Dict[str, Counter] = {}

    for row in data:
        path = row.get("image_path")
        label = row.get("label") or row.get("disease")
        if not path or not label or not os.path.exists(path):
            continue
        result = engine.predict(path)
        pred = result["disease"]["name"]
        y_true.append(label)
        y_pred.append(pred)
        if not evaluable(row):
            continue
        t_true.append(label)
        t_pred.append(pred)
        per_label.setdefault(label, Counter())[pred] += 1
        if row.get("crop"):
            crop_n += 1
            crop_ok += int(result["crop"]["name"] == row["crop"])

    if not y_true:
        return {"error": "评测集中没有可用样本"}

    def _stats(truth, preds):
        return {
            "n": len(truth),
            "accuracy": round(sum(1 for t, p in zip(truth, preds) if t == p) / len(truth), 4),
            "macro_f1": round(_macro_f1(truth, preds), 4),
        }

    recalls = {
        label: {
            "support": sum(counter.values()),
            "recall": round(counter.get(label, 0) / sum(counter.values()), 4),
            "trained": label in trained_set,
        }
        for label, counter in per_label.items()
    }
    return {
        "all": _stats(y_true, y_pred),
        "trained": _stats(t_true, t_pred),
        "crop_accuracy": round(crop_ok / crop_n, 4) if crop_n else None,
        "per_label": dict(sorted(recalls.items(), key=lambda kv: -kv[1]["support"])),
    }


def _pct(v) -> str:
    return f"{v * 100:.2f}%" if isinstance(v, (int, float)) else "—"


def _num(v) -> str:
    return f"{v:.4f}" if isinstance(v, (int, float)) else "—"


def build_report(args) -> str:
    checkpoints = Path(args.checkpoints)
    reports = Path(args.reports)
    production = Path(args.production)

    meta = _checkpoint_meta(str(production)) if production.exists() else {}
    version = meta.get("version") or production.stem
    versions = _collect_versions(checkpoints)

    lines: List[str] = []
    lines.append("# CNN 基线指标报告（P0 验收）")
    lines.append("")
    lines.append(f"> 本文件由 `training/make_cnn_metrics.py` 自动生成，请勿手工编辑。")
    lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"> 生产权重：`{production.as_posix()}`（version={version}）")
    lines.append("")

    lines.append("## 1. 模型与标签")
    lines.append("")
    lines.append("| 项 | 值 |")
    lines.append("|---|---|")
    lines.append(f"| 标签版本 | `{meta.get('labels_version') or '—'}` |")
    lines.append(f"| 最佳 epoch | {meta.get('epoch') or '—'} |")
    trained = meta.get("trained_classes") or []
    lines.append(f"| 有训练数据的类别 | {len(trained)} 类 |")
    if trained:
        lines.append(f"| 训练类 | {'、'.join(trained)} |")
    lines.append("| 骨干 | MobileNetV3-Small（约 5.6 MB） |")
    lines.append("")

    lines.append("## 2. 同域指标")
    lines.append("")
    lines.append("### 2.1 训练脚本自测（原始 argmax，无推理后处理）")
    lines.append("")
    lines.append("| 版本 | 增强 | 训练样本 | val acc | val macro-F1 | test acc | test macro-F1 | 最佳轮 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for row in versions:
        mark = " **（生产）**" if row["tag"] == version else ""
        lines.append(
            f"| `{row['tag']}`{mark} | {row['aug']} | {row['n_train']} | "
            f"{_pct(row['val_acc'])} | {_num(row['val_f1'])} | "
            f"{_pct(row['test_acc'])} | {_num(row['test_f1'])} | {row['best_epoch']} |"
        )
    lines.append("")

    gate = None
    if not args.skip_eval:
        gate = _evaluate(str(production), args.gate_dataset, trained, args.img_size)

    lines.append("### 2.2 生产推理路径（含零样本屏蔽 + 作物一致性约束）")
    lines.append("")
    if gate and not gate.get("error"):
        all_stats = gate["all"]
        t_stats = gate["trained"]
        lines.append(f"评测集：`{args.gate_dataset}`")
        lines.append("")
        lines.append("| 口径 | 样本 | 病害准确率 | macro-F1 |")
        lines.append("|---|---|---|---|")
        lines.append(f"| 全量 | {all_stats['n']} | {_pct(all_stats['accuracy'])} | {_num(all_stats['macro_f1'])} |")
        lines.append(f"| **仅训练类** | {t_stats['n']} | **{_pct(t_stats['accuracy'])}** | **{_num(t_stats['macro_f1'])}** |")
        lines.append("")
        lines.append(f"训练类上的作物头准确率：**{_pct(gate.get('crop_accuracy'))}**")
        lines.append("")
        lines.append("> 与 2.1 的差异来自两点：(1) 推理后处理——未训练类概率置零后再归一化，")
        lines.append("> 且病害类别必须与预测作物一致；(2) 评测集在加入菠萝后重建，")
        lines.append("> 当前清单包含菠萝的 2 个未训练病害类和 74 张菠萝健康图（标签为“健康”，")
        lines.append("> 但作物头从未训练过菠萝）。“仅训练类”同时要求病害与作物都在训练范围内，")
        lines.append("> 因此才是与 2.1 可比的同域指标。")
    else:
        reason = (gate or {}).get("error") or "已跳过模型评测（--skip-eval）"
        lines.append(f"本次未重跑：{reason}")
    lines.append("")

    flywheel = _collect_flywheel(checkpoints)
    if flywheel:
        lines.append("### 2.3 飞轮候选（LoRA，指标口径不同）")
        lines.append("")
        lines.append("| 候选 | 基座 | 飞轮样本 | 回放样本 | 留出集微调前 | 留出集微调后 |")
        lines.append("|---|---|---|---|---|---|")
        for row in flywheel:
            before = (row["before"] or {}).get("accuracy") if isinstance(row["before"], dict) else row["before"]
            after = (row["after"] or {}).get("accuracy") if isinstance(row["after"], dict) else row["after"]
            lines.append(
                f"| `{row['tag']}` | {row['base']} | {row['flywheel']} | {row['replay']} | "
                f"{_pct(before)} | {_pct(after)} |"
            )
        lines.append("")
        lines.append("> 六版候选均因跨域回退被门禁拒绝，详见 `docs/flywheel.md`。")
        lines.append("")

    xdom_path = _pick_cross_domain(reports, version)
    lines.append("## 3. 跨域指标")
    lines.append("")
    if xdom_path and Path(xdom_path).exists():
        data = _load_json(xdom_path) or []
        lines.append(f"来源：`{Path(xdom_path).as_posix()}`")
        lines.append("")
        lines.append("| 评测集 | 样本 | 准确率 | macro-F1 |")
        lines.append("|---|---|---|---|")
        for item in data:
            lines.append(
                f"| {item.get('dataset')} | {item.get('n')} | "
                f"{_pct(item.get('accuracy'))} | {_num(item.get('macro_f1'))} |"
            )
        lines.append("")
        lines.append("> 芒果与埃塞俄比亚咖啡为真跨域（来源未参与训练）；")
        lines.append("> 其余留出集与训练同源，只能说明未退步，不能当作泛化证据。")
    else:
        lines.append("未找到生产版本对应的跨域报告。")
    lines.append("")

    lines.append("## 4. 逐类召回（生产推理路径）")
    lines.append("")
    if gate and not gate.get("error"):
        lines.append("| 类别 | 样本 | 召回 |")
        lines.append("|---|---|---|")
        for label, st in gate["per_label"].items():
            lines.append(f"| {label} | {st['support']} | {st['recall']:.4f} |")
        lines.append("")
        lines.append("> 表中只统计病害与作物都在训练范围内的样本；")
        lines.append("> 菠萝的 2 个未训练类与 74 张菠萝健康图不在本口径内。")
    else:
        lines.append("本次未重跑模型；逐类指标见 `checkpoints/<tag>/metrics.json` 的 `test.per_class`。")
    lines.append("")

    lines.append("## 5. 评测口径与注意事项")
    lines.append("")
    lines.append("1. **同域不等于可用**：2.1 / 2.2 的评测集与训练数据同来源；真实泛化看第 3 节。")
    lines.append("2. **10 个训练类**：12 类标签中有 2 类没有训练数据，推理时概率被置零。")
    lines.append("3. **严重度不评估**：公开数据无严重度标注，报告显示“未评估”。")
    lines.append("4. **门禁用固定容差与 bootstrap**：准确率 0.5pt 硬容差；macro-F1 看差值的 95% CI 是否整体低于 0。")
    lines.append("5. **评测集与训练清单同源**：不要用本报告的数字推断田间准确率。")
    lines.append("")

    lines.append("## 6. 复现")
    lines.append("")
    lines.append("```bash")
    lines.append("cd zhinong-huiyan/ai-model")
    lines.append("python training/make_cnn_metrics.py")
    lines.append("")
    lines.append("# 只汇总已有指标、不加载模型")
    lines.append("python training/make_cnn_metrics.py --skip-eval")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoints", default="checkpoints")
    ap.add_argument("--reports", default="reports")
    ap.add_argument("--production", default="checkpoints/best.pt")
    ap.add_argument("--gate-dataset", default="data/manifests/v1_test.json")
    ap.add_argument("--img-size", type=int, default=224)
    ap.add_argument("--out", default="reports/cnn_metrics.md")
    ap.add_argument("--skip-eval", action="store_true", help="不加载模型，只汇总已有指标")
    args = ap.parse_args()

    text = build_report(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"已写入 {out}")


if __name__ == "__main__":
    main()
