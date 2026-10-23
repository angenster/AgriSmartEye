"""
Agent 级评测（方案 §10.2 / §10.3）。

在固定评测集上逐张跑完整诊断 Agent，统计：
  - 病种准确率（Agent 最终结论 vs 真值）与 CNN 基线准确率（同一次运行的 top1）
  - 升级率 / 升级成功率（是否调用 escalate_vlm）
  - needs_human 率、证据核对通过率
  - 平均步数、耗时、成本

评测运行使用 trigger="eval"：**不进入数据飞轮复核队列**，避免把评测集灌进
真实样本队列；同时 user_id=None，不会出现在测试账号的运行历史里。

用法（在 backend/ 目录下）：
    python -m flywheel.eval_agent \
        --dataset ../ai-model/data/manifests/v1_test.json \
        --per-class 10 --out ../ai-model/reports/agent_metrics.md
"""
import argparse
import json
import os
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# ai-model 下的 labels / 权重
AI_MODEL_DIR = Path(__file__).resolve().parents[2] / "ai-model"
if str(AI_MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(AI_MODEL_DIR))

import torch

from agent import config
from agent.loop import run_agent
from database import SessionLocal
from labels import crop_of_label
from services.model_service import model_service


def _load_trained(weights: Path) -> List[str]:
    ckpt = torch.load(weights, map_location="cpu")
    return list(ckpt.get("trained_classes") or [])


def load_samples(dataset: Path, trained: List[str], per_class: int, seed: int) -> List[Dict]:
    """只取“病害与作物都在训练范围内”的样本，按类别分层抽样。"""
    data = json.loads(dataset.read_text(encoding="utf-8"))
    trained_set = set(trained)
    trained_crops = {crop_of_label(label) for label in trained_set if crop_of_label(label)}

    by_label: Dict[str, List[Dict]] = defaultdict(list)
    for row in sorted(data, key=lambda r: r.get("image_path") or ""):
        label = row.get("label") or row.get("disease")
        crop = row.get("crop")
        path = row.get("image_path")
        if not label or not path:
            continue
        if label not in trained_set:
            continue
        if crop and crop not in trained_crops:
            continue
        if not Path(path).exists():
            continue
        by_label[label].append(row)

    rnd = random.Random(seed)
    picked: List[Dict] = []
    for label in sorted(by_label):
        items = by_label[label][:]
        rnd.shuffle(items)
        picked.extend(items[:per_class])
    rnd.shuffle(picked)
    return picked


def _step(result: Dict, tool: str, ok: Optional[bool] = None) -> Optional[Dict]:
    for step in result.get("steps") or []:
        if step.get("tool_name") != tool:
            continue
        if ok is not None and bool(step.get("ok")) != ok:
            continue
        return step
    return None


def evaluate(samples: List[Dict]) -> Dict:
    rows = []
    for i, sample in enumerate(samples, 1):
        truth = sample.get("label") or sample.get("disease")
        db = SessionLocal()
        try:
            result = run_agent(
                db,
                sample["image_path"],
                user_id=None,
                field_id=None,
                trigger="eval",
            )
        finally:
            db.close()

        report = result.get("report") or {}
        final = ((report.get("disease") or {}).get("name"))
        cnn_step = _step(result, "run_cnn_detect", ok=True)
        cnn_pred = ((cnn_step or {}).get("result") or {}).get("disease")
        escalation_step = _step(result, "escalate_vlm")
        escalation_ok = _step(result, "escalate_vlm", ok=True) is not None

        rows.append({
            "truth": truth,
            "final": final,
            "cnn": cnn_pred,
            "agent_ok": final == truth,
            "cnn_ok": cnn_pred == truth,
            "escalated": escalation_step is not None,
            "escalation_ok": escalation_ok,
            "needs_human": bool(report.get("needs_human")),
            "evidence_valid": bool(result.get("evidence_valid")),
            "status": result.get("status"),
            "steps": result.get("steps_used") or 0,
            "latency_ms": (report.get("cost") or {}).get("latency_ms") or 0.0,
            "vlm_calls": (report.get("cost") or {}).get("vlm_calls") or 0,
            "planner": result.get("planner"),
        })
        if i % 10 == 0:
            print(f"  {i}/{len(samples)} 已完成")

    return {"rows": rows, "n": len(rows)}


def _rate(rows: List[Dict], key: str) -> float:
    return round(sum(1 for r in rows if r[key]) / len(rows), 4) if rows else 0.0


def _acc(rows: List[Dict], key: str) -> float:
    return round(sum(1 for r in rows if r[key]) / len(rows), 4) if rows else 0.0


def _display_path(path: str) -> str:
    """报告里用相对仓库根目录的路径，避免写入本机绝对路径。"""
    root = Path(__file__).resolve().parents[2]
    try:
        return Path(os.path.relpath(path, root)).as_posix()
    except ValueError:
        return Path(path).name


def build_report(result: Dict, args) -> str:
    rows = result["rows"]
    n = result["n"]
    agent_acc = _acc(rows, "agent_ok")
    cnn_acc = _acc(rows, "cnn_ok")
    delta = round(agent_acc - cnn_acc, 4)
    esc = [r for r in rows if r["escalated"]]
    non_esc = [r for r in rows if not r["escalated"]]
    per_class = defaultdict(list)
    for r in rows:
        per_class[r["truth"]].append(r)

    planner = next((r["planner"] for r in rows if r["planner"]), "unknown")
    avg = lambda key: round(sum(r[key] for r in rows) / n, 1) if n else 0

    lines = [
        "# Agent 级评测报告",
        "",
        "> 由 `python -m flywheel.eval_agent` 自动生成，请勿手工编辑。",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"> 评测集：`{_display_path(args.dataset)}`（每类最多 {args.per_class} 张）",
        f"> 样本数：{n} | planner：`{planner}` | VLM 已配置："
        f"{'是' if config.vlm_configured() else '否'}",
        "",
        "## 1. 总览",
        "",
        "| 指标 | 值 |",
        "|---|---|",
        f"| Agent 病种准确率 | **{agent_acc * 100:.2f}%** |",
        f"| CNN 基线准确率（同批样本） | **{cnn_acc * 100:.2f}%** |",
        f"| 相对 CNN 增益 | {'+' if delta >= 0 else ''}{delta * 100:.2f} pt |",
        f"| 升级率（调用 VLM 的比例） | {_rate(rows, 'escalated') * 100:.2f}% |",
        f"| 升级成功率 | {_rate(rows, 'escalation_ok') * 100:.2f}% |",
        f"| needs_human 率 | {_rate(rows, 'needs_human') * 100:.2f}% |",
        f"| 证据核对通过率 | {_rate(rows, 'evidence_valid') * 100:.2f}% |",
        f"| 平均步数 | {avg('steps'):.1f} |",
        f"| 平均耗时 | {avg('latency_ms'):.0f} ms |",
        "",
    ]

    if not config.vlm_configured():
        lines += [
            "> **重要**：本次评测未配置 `VLM_API_KEY`。所有升级尝试都会失败，",
            "> Agent 只能采纳 CNN 结论，因此“相对 CNN 增益”按构造为 0。",
            "> 这一行数字衡量的是“没有第二引擎时的 Agent”，不是双引擎的完整能力。",
            "",
        ]

    lines += [
        "## 2. 升级子集分析",
        "",
        "| 子集 | 样本 | Agent 准确率 | CNN 准确率 |",
        "|---|---|---|---|",
        f"| 触发升级 | {len(esc)} | {_acc(esc, 'agent_ok') * 100:.2f}% | {_acc(esc, 'cnn_ok') * 100:.2f}% |",
        f"| 未触发升级 | {len(non_esc)} | {_acc(non_esc, 'agent_ok') * 100:.2f}% | {_acc(non_esc, 'cnn_ok') * 100:.2f}% |",
        "",
        "> 未配置 VLM 时，触发升级的样本仍会回退到 CNN 结论，两个子集的差异只反映",
        "> “哪些样本被仲裁规则判定为不确定”，不代表升级带来的提升。",
        "",
        "## 3. 逐类结果",
        "",
        "| 类别 | 样本 | Agent 准确率 | CNN 准确率 | 触发升级 |",
        "|---|---|---|---|---|",
    ]
    for label in sorted(per_class, key=lambda k: -len(per_class[k])):
        items = per_class[label]
        lines.append(
            f"| {label} | {len(items)} | {_acc(items, 'agent_ok') * 100:.2f}% | "
            f"{_acc(items, 'cnn_ok') * 100:.2f}% | {sum(1 for r in items if r['escalated'])} |"
        )

    status_counts = Counter(r["status"] for r in rows)
    lines += [
        "",
        "## 4. 运行状态分布",
        "",
        "| 状态 | 次数 |",
        "|---|---|",
    ]
    for status, count in status_counts.most_common():
        lines.append(f"| {status} | {count} |")

    lines += [
        "",
        "## 5. 口径与注意事项",
        "",
        "1. 评测集来自公开数据集的同域测试划分，**不代表田间表现**；跨域指标见 `cnn_metrics.md`。",
        "2. 只统计“病害与作物都在训练范围内”的样本，菠萝等未训练类已排除。",
        "3. 评测运行使用 `trigger=\"eval\"`，不会进入复核队列，也不属于任何用户的历史记录。",
        "4. 引用可核对率由 `verify_evidence` 程序判定，不依赖模型自述。",
        "",
        "## 6. 复现",
        "",
        "```bash",
        "cd zhinong-huiyan/backend",
        "python -m flywheel.eval_agent --dataset ../ai-model/data/manifests/v1_test.json \\",
        "    --per-class 10 --out ../ai-model/reports/agent_metrics.md",
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Agent 级评测")
    ap.add_argument("--dataset", default=str(AI_MODEL_DIR / "data/manifests/v1_test.json"))
    ap.add_argument("--weights", default=str(AI_MODEL_DIR / "checkpoints/best.pt"))
    ap.add_argument("--per-class", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 张，用于冒烟测试")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=str(AI_MODEL_DIR / "reports/agent_metrics.md"))
    args = ap.parse_args()

    if not Path(args.dataset).exists():
        raise SystemExit(f"评测集不存在: {args.dataset}")

    model_service.weights_path = args.weights
    model_service.load()
    if not model_service.is_ready:
        raise SystemExit(f"模型加载失败: {model_service.load_error}")

    samples = load_samples(Path(args.dataset), _load_trained(Path(args.weights)),
                           args.per_class, args.seed)
    if args.limit:
        samples = samples[: args.limit]
    if not samples:
        raise SystemExit("没有可用样本")
    print(f"评测样本: {len(samples)} 张 | planner={config.llm_configured() and 'llm' or 'rule_based'}"
          f" | VLM={'on' if config.vlm_configured() else 'off'}")

    result = evaluate(samples)
    text = build_report(result, args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"已写入 {out}")


if __name__ == "__main__":
    main()
