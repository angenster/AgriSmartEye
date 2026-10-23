"""
评测门禁（方案 §7.5）—— candidate 只有不比现网差，才允许上线。

判定规则（全部满足才 promote）：
    disease accuracy  >= production.accuracy - tolerance
    disease macro-F1  >= production.macro_f1 - tolerance
    severity accuracy >= production.severity_accuracy      （不允许回退）

任一不满足 → candidate 置为 archived，并完整记录 eval_runs 供追溯。
评测集必须是固定的（不随飞轮变化），否则指标没有可比性。

评测集清单格式（JSON 数组）：
    [{"image_path": "...", "crop": "芒果", "disease": "芒果炭疽病", "severity": "中度"}, ...]
crop / severity 可缺省，缺省则不参与该项统计。
"""
import json
import os
import random
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from models import EvalRun, ModelVersion

DEFAULT_TOLERANCE = 0.005   # 0.5 个百分点


# ---------------------------------------------------------------- 指标

def macro_f1(y_true: List[str], y_pred: List[str]) -> float:
    """多分类宏平均 F1（不引 sklearn）。

    只统计在 y_true 中真实出现过的类别：固定评测集未必覆盖全部 12 类，
    若把"模型误预测但测试集没有的类"也算进平均，分母会随模型行为浮动，
    不同版本之间不可比。误预测到空类的影响已由 accuracy 与各类 precision 反映。
    """
    if not y_true:
        return 0.0
    labels = set(y_true)
    scores = []
    for label in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        scores.append(2 * precision * recall / (precision + recall) if (precision + recall) else 0.0)
    return sum(scores) / len(scores)


def _accuracy(y_true: List[str], y_pred: List[str]) -> Optional[float]:
    if not y_true:
        return None
    return sum(1 for t, p in zip(y_true, y_pred) if t == p) / len(y_true)


# ---------------------------------------------------------------- 评测

def load_manifest(dataset_path: str) -> List[Dict]:
    """读取评测集清单。文件不存在直接报错，不做静默的空评测。"""
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(
            f"评测集清单不存在: {dataset_path}。门禁必须跑在固定评测集上，"
            "否则候选与现网的指标没有可比性。"
        )
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list) or not data:
        raise ValueError(f"评测集清单为空或格式不对: {dataset_path}")

    missing = [d["image_path"] for d in data if not os.path.exists(d.get("image_path", ""))]
    if missing:
        raise FileNotFoundError(
            f"评测集中有 {len(missing)} 张图像不存在，例如 {missing[0]!r}"
        )
    return data


def evaluate_checkpoint(
    weights_path: Optional[str],
    manifest: List[Dict],
    allow_demo: bool = False,
    return_predictions: bool = False,
) -> Dict:
    """在给定清单上评测一个权重文件。

    return_predictions=True 时额外返回逐样本的 (真实, 预测)，供 bootstrap
    显著性检验使用；这些私有字段在落库前会被移除。
    """
    from services.model_service import ModelService

    service = ModelService()
    service.weights_path = weights_path or ""
    service.backend = os.getenv("MODEL_BACKEND", "pytorch")
    service.device = os.getenv("MODEL_DEVICE", "auto")
    service.allow_demo = allow_demo
    service.load()
    if not service.is_ready:
        raise RuntimeError(f"加载权重失败 {weights_path!r}: {service.load_error}")

    crop_true, crop_pred = [], []
    dis_true, dis_pred = [], []
    sev_true, sev_pred = [], []

    for row in manifest:
        pred = service.predict(row["image_path"])
        if row.get("crop"):
            crop_true.append(row["crop"])
            crop_pred.append(pred["crop"]["name"])
        # 训练清单用 label 字段，历史评测清单用 disease；两者都接受
        disease_label = row.get("disease") or row.get("label")
        if disease_label:
            dis_true.append(disease_label)
            dis_pred.append(pred["disease"]["name"])
        # 严重度没有训练数据（labels.SEVERITY_TRAINED=False），
        # 只有评测清单显式提供 severity 时才统计，避免拿随机头蒙出指标
        if row.get("severity"):
            sev_true.append(row["severity"])
            sev_pred.append(pred["severity"]["name"])

    result = {
        "n": len(manifest),
        "weights_path": weights_path,
        "is_demo": service.is_demo,
        "crop_accuracy": _accuracy(crop_true, crop_pred),
        "disease_accuracy": _accuracy(dis_true, dis_pred),
        "disease_macro_f1": round(macro_f1(dis_true, dis_pred), 4),
        "severity_accuracy": _accuracy(sev_true, sev_pred),
    }
    if return_predictions:
        result["_dis_true"] = dis_true
        result["_dis_pred"] = dis_pred
    return result


# ---------------------------------------------------------------- 门禁

def _fmt(v: Optional[float]) -> str:
    return "n/a" if v is None else f"{v:.4f}"


def bootstrap_macro_f1_ci(
    y_true: List[str],
    pred_production: List[str],
    pred_candidate: List[str],
    n_boot: int = 1000,
    seed: int = 42,
) -> Optional[Tuple[float, float]]:
    """估计 macro-F1 差值（candidate - production）的 95% 置信区间。

    为什么需要它：固定 0.5pt 阈值在小评测集上会把噪声当回退。
    本项目的门禁集只有约 600 张，部分类别仅 7–9 张，macro-F1 的标准误
    可达数个百分点。用 bootstrap 只在差异显著（CI 整体低于 0）时才判回退，
    并且评测集越大 CI 越窄、门禁会自动变严。
    """
    n = len(y_true)
    if n == 0 or len(pred_production) != n or len(pred_candidate) != n:
        return None
    rng = random.Random(seed)
    diffs = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        yy = [y_true[i] for i in idx]
        pa = [pred_production[i] for i in idx]
        pb = [pred_candidate[i] for i in idx]
        diffs.append(macro_f1(yy, pb) - macro_f1(yy, pa))
    diffs.sort()
    return (round(diffs[int(0.025 * n_boot)], 4), round(diffs[int(0.975 * n_boot)], 4))


def compare(
    candidate: Dict,
    production: Optional[Dict],
    tolerance: float = DEFAULT_TOLERANCE,
    macro_ci: Optional[Tuple[float, float]] = None,
) -> Tuple[bool, List[str]]:
    """返回 (是否通过, 未通过的原因列表)。

    准确率用固定容差硬门禁；macro-F1 若提供了 bootstrap CI，
    则以"差异是否显著"为准（CI 上界 < 0 才算回退）。
    """
    if production is None:
        # 没有现网基线时，candidate 即为首个版本，直接放行但标注清楚
        return True, ["无现网基线，本次作为首个版本直接采纳"]

    failures: List[str] = []

    c_acc, p_acc = candidate.get("disease_accuracy"), production.get("disease_accuracy")
    if c_acc is not None and p_acc is not None and c_acc < p_acc - tolerance:
        failures.append(f"病害准确率回退：{_fmt(c_acc)} < {_fmt(p_acc)} - {tolerance}")

    c_f1, p_f1 = candidate.get("disease_macro_f1"), production.get("disease_macro_f1")
    if c_f1 is not None and p_f1 is not None:
        if macro_ci is not None:
            if macro_ci[1] < 0:
                failures.append(
                    f"病害 macro-F1 显著回退：Δ 的 95% CI 上界 {macro_ci[1]:+.4f} < 0"
                )
        elif c_f1 < p_f1 - tolerance:
            failures.append(f"病害 macro-F1回退：{_fmt(c_f1)} < {_fmt(p_f1)} - {tolerance}")

    c_sev, p_sev = candidate.get("severity_accuracy"), production.get("severity_accuracy")
    if c_sev is not None and p_sev is not None and c_sev < p_sev:
        failures.append(f"严重度准确率回退：{_fmt(c_sev)} < {_fmt(p_sev)}")

    return (not failures), failures


def run_gate(
    db: Session,
    candidate_weights: str,
    candidate_tag: str,
    dataset_path: str,
    base_version: Optional[str] = None,
    tolerance: float = DEFAULT_TOLERANCE,
    allow_demo: bool = False,
    cross_domain: Optional[List[str]] = None,
) -> Dict:
    """对 candidate 跑门禁，写 eval_runs 与 model_versions，返回判定结果。

    cross_domain: 可选的跨域评测清单列表。任一清单上准确率回退超过容差即拒绝。
    同域指标会掩盖"换环境就崩"的问题，飞轮的候选必须同时通过跨域检查。
    """
    manifest = load_manifest(dataset_path)
    dataset_name = os.path.basename(dataset_path)

    production = (
        db.query(ModelVersion).filter(ModelVersion.status == "production").first()
    )
    prod_metrics = None
    prod_preds = None
    if production is not None:
        if not production.weights_path:
            # 历史遗留的 demo / 冒烟版本没有真实权重，不能作为基线；
            # 否则门禁会去加载空路径并直接失败。
            production = None
        else:
            prod_raw = evaluate_checkpoint(production.weights_path, manifest,
                                           allow_demo=allow_demo, return_predictions=True)
            prod_preds = (prod_raw.pop("_dis_true", None), prod_raw.pop("_dis_pred", None))
            prod_metrics = prod_raw
            db.add(EvalRun(model_version_id=production.id, dataset_name=dataset_name,
                           metrics_json=prod_metrics))

    cand_raw = evaluate_checkpoint(candidate_weights, manifest,
                                   allow_demo=allow_demo, return_predictions=True)
    cand_preds = (cand_raw.pop("_dis_true", None), cand_raw.pop("_dis_pred", None))
    cand_metrics = cand_raw

    macro_ci = None
    if prod_preds and cand_preds and prod_preds[0] and cand_preds[1]:
        macro_ci = bootstrap_macro_f1_ci(prod_preds[0], prod_preds[1], cand_preds[1])

    passed, notes = compare(cand_metrics, prod_metrics, tolerance, macro_ci=macro_ci)

    # ---- 跨域非回退检查 ----
    cross_results = []
    if cross_domain:
        for cd_path in cross_domain:
            cd_path = cd_path.strip()
            if not cd_path:
                continue
            cd_manifest = load_manifest(cd_path)
            cd_name = os.path.basename(cd_path)
            cand_cd = evaluate_checkpoint(candidate_weights, cd_manifest, allow_demo=allow_demo)
            prod_cd = None
            if production is not None:
                prod_cd = evaluate_checkpoint(production.weights_path, cd_manifest,
                                              allow_demo=allow_demo)
            entry = {"dataset": cd_name, "n": len(cd_manifest),
                     "candidate": cand_cd.get("disease_accuracy"),
                     "production": prod_cd.get("disease_accuracy") if prod_cd else None}
            if prod_cd is not None and cand_cd.get("disease_accuracy") is not None:
                if cand_cd["disease_accuracy"] < prod_cd["disease_accuracy"] - tolerance:
                    passed = False
                    notes.append(
                        f"跨域准确率回退（{cd_name}）：{_fmt(cand_cd['disease_accuracy'])}"
                        f" < {_fmt(prod_cd['disease_accuracy'])} - {tolerance}"
                    )
            cross_results.append(entry)

    version = db.query(ModelVersion).filter(ModelVersion.version_tag == candidate_tag).first()
    if version is None:
        version = ModelVersion(version_tag=candidate_tag, base_version=base_version,
                               weights_path=candidate_weights)
        db.add(version)
        db.flush()
    version.weights_path = candidate_weights
    version.eval_metrics_json = cand_metrics
    version.status = "candidate"

    db.add(EvalRun(model_version_id=version.id, dataset_name=dataset_name,
                   metrics_json=cand_metrics))

    if passed:
        # 旧 production 降级为 archived，新版本上位
        for other in db.query(ModelVersion).filter(ModelVersion.status == "production").all():
            other.status = "archived"
        version.status = "production"
        version.promoted_at = datetime.utcnow()
    else:
        version.status = "archived"

    db.commit()

    return {
        "candidate": candidate_tag,
        "candidate_metrics": cand_metrics,
        "production_metrics": prod_metrics,
        "passed": passed,
        "decision": "promoted" if passed else "archived",
        "notes": notes,
        "tolerance": tolerance,
        "macro_f1_delta_ci": macro_ci,
        "cross_domain": cross_results,
        "dataset": dataset_name,
        "n": len(manifest),
    }


def list_versions(db: Session) -> List[Dict]:
    rows = db.query(ModelVersion).order_by(ModelVersion.created_at.desc()).all()
    return [
        {
            "version_tag": v.version_tag,
            "status": v.status,
            "base_version": v.base_version,
            "weights_path": v.weights_path,
            "metrics": v.eval_metrics_json,
            "promoted_at": v.promoted_at.isoformat() if v.promoted_at else None,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in rows
    ]


def list_eval_runs(db: Session, limit: int = 20) -> List[Dict]:
    rows = (
        db.query(EvalRun).order_by(EvalRun.created_at.desc()).limit(max(1, min(limit, 200))).all()
    )
    return [
        {
            "id": r.id,
            "model_version_id": r.model_version_id,
            "dataset_name": r.dataset_name,
            "metrics": r.metrics_json,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def main() -> None:
    """命令行入口：python -m flywheel.gate --candidate <weights> --tag <tag> --dataset <manifest>"""
    import argparse

    from database import SessionLocal

    parser = argparse.ArgumentParser(description="模型评测门禁")
    parser.add_argument("--candidate", required=True, help="候选权重路径")
    parser.add_argument("--tag", required=True, help="候选版本号")
    parser.add_argument("--dataset", required=True, help="评测集清单 JSON 路径")
    parser.add_argument("--base-version", default=None)
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    parser.add_argument("--allow-demo", action="store_true",
                        help="允许加载未训练权重（仅用于打通流程）")
    parser.add_argument("--cross-domain", default=None,
                        help="逗号分隔的跨域评测清单；任一集准确率回退超过容差则拒绝")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = run_gate(db, args.candidate, args.tag, args.dataset,
                          base_version=args.base_version,
                          tolerance=args.tolerance,
                          allow_demo=args.allow_demo,
                          cross_domain=args.cross_domain.split(",") if args.cross_domain else None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
