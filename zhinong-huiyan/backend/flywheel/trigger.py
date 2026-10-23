"""
飞轮触发（方案 §7.2）—— 判断一次诊断是否值得进入复核队列。

三个触发条件：
    low_conf          CNN 病害置信度低于 τ_low
    cnn_vlm_disagree  升级 VLM 后两者给出的病名不一致
    vlm_low_conf      VLM 自己对结果也没把握

另有 manual：人工（或前端）显式标记的样本，走同一个入口入队。

入队与"是否升级 VLM"解耦：按方案 §5.4，只要升级过就无条件入队，
因为升级本身已经是"模型拿不准"的证据。
"""
import hashlib
import os
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from agent import config
from models import SampleQueue, SampleStatus

MIN_REVIEW_POINTS = 10       # 采纳预标注的积分
CORRECT_REWARD_POINTS = 20   # 修正标签的积分更高（信息量更大）


def image_hash(path: str) -> str:
    """按内容哈希，同一张图换文件名也视为同一样本"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def compute_trigger_reasons(cnn: Dict, vlm: Optional[Dict]) -> List[str]:
    """按方案 §7.2 判定触发原因。"""
    reasons: List[str] = []

    conf = float((cnn or {}).get("confidence") or 0.0)
    if conf < config.TAU_LOW:
        reasons.append("low_conf")

    if vlm:
        if vlm.get("disease") and cnn.get("disease") and vlm["disease"] != cnn["disease"]:
            reasons.append("cnn_vlm_disagree")
        if float(vlm.get("confidence") or 0.0) < config.TAU_LOW:
            reasons.append("vlm_low_conf")

    return reasons


def _already_pending(db: Session, digest: str) -> bool:
    return (
        db.query(SampleQueue)
        .filter(SampleQueue.image_hash == digest,
                SampleQueue.status == SampleStatus.pending)
        .first()
        is not None
    )


def maybe_enqueue(
    db: Session,
    image_path: str,
    cnn: Dict,
    vlm: Optional[Dict] = None,
    source: str = "agent_run",
    run_id: Optional[int] = None,
    field_id: Optional[int] = None,
    manual: bool = False,
) -> Optional[Dict]:
    """满足条件则入队，返回队列条目信息；否则返回 None。"""
    if not image_path or not os.path.exists(image_path):
        return None

    reasons = compute_trigger_reasons(cnn, vlm)
    if manual:
        reasons.append("manual")
    if not reasons:
        return None

    digest = image_hash(image_path)
    if _already_pending(db, digest):
        return {"skipped": True, "reason": "duplicate_pending", "image_hash": digest}

    topk = (cnn or {}).get("topk") or []
    item = SampleQueue(
        image_path=image_path,
        image_hash=digest,
        source=source,
        run_id=run_id,
        field_id=field_id,
        crop_type=(cnn or {}).get("crop"),
        cnn_top1=(cnn or {}).get("disease"),
        cnn_conf=(cnn or {}).get("confidence"),
        cnn_topk_json=topk,
        vlm_pred=(vlm or {}).get("disease"),
        vlm_conf=(vlm or {}).get("confidence"),
        vlm_rationale=(vlm or {}).get("rationale"),
        trigger_reason="|".join(reasons),
        status=SampleStatus.pending,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    return {
        "sample_id": item.id,
        "trigger_reason": item.trigger_reason,
        "image_hash": digest,
        "cnn_top1": item.cnn_top1,
        "cnn_conf": item.cnn_conf,
        "vlm_pred": item.vlm_pred,
    }
