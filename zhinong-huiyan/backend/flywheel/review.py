"""
复核队列（方案 §7.3）—— 列表、确认、统计。

设计取舍：
  - 队列是**只进不改**的：确认后不覆盖原记录，而是在 sample_confirmations
    追加一条结论，sample_queue.status 随之流转。这样每次复核都可追溯，
    也避免"改错了标签导致训练数据被污染且无从查证"。
  - 标签必须落在已知类别内（或显式选 UNKNOWN_LABEL），否则拒收。
    飞轮的输入质量直接决定微调质量，这里不做"尽力而为"的猜测。
"""
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from flywheel.trigger import CORRECT_REWARD_POINTS, MIN_REVIEW_POINTS
from labels import DISEASE_CLASSES, UNKNOWN_LABEL
from models import SampleConfirmation, SampleQueue, SampleStatus

VALID_LABELS = set(DISEASE_CLASSES) | {UNKNOWN_LABEL}

# 分歧样本信息量最大，优先复核
_PRIORITY_SQL = (
    "CASE WHEN trigger_reason LIKE '%cnn_vlm_disagree%' THEN 0 "
    "WHEN trigger_reason LIKE '%low_conf%' THEN 1 ELSE 2 END"
)


def _serialize(item: SampleQueue, confirmation: Optional[SampleConfirmation] = None) -> Dict:
    return {
        "sample_id": item.id,
        "image_path": item.image_path,
        "source": item.source,
        "run_id": item.run_id,
        "cnn_top1": item.cnn_top1,
        "cnn_conf": item.cnn_conf,
        "cnn_topk": item.cnn_topk_json,
        "vlm_pred": item.vlm_pred,
        "vlm_conf": item.vlm_conf,
        "vlm_rationale": item.vlm_rationale,
        "trigger_reason": (item.trigger_reason or "").split("|"),
        "status": item.status.value if hasattr(item.status, "value") else item.status,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "confirmation": None if confirmation is None else {
            "final_label": confirmation.final_label,
            "confirm_source": confirmation.confirm_source,
            "points": confirmation.points,
            "notes": confirmation.notes,
            "confirmed_by": confirmation.confirmed_by,
            "created_at": confirmation.created_at.isoformat() if confirmation.created_at else None,
        },
    }


def list_queue(
    db: Session,
    status: str = "pending",
    limit: int = 20,
    offset: int = 0,
) -> List[Dict]:
    """列出队列条目。pending 时按触发原因优先级排序（分歧优先）。"""
    query = db.query(SampleQueue)

    if status != "all":
        try:
            query = query.filter(SampleQueue.status == SampleStatus(status))
        except ValueError:
            raise ValueError(f"未知状态: {status}")

    if status == "pending":
        query = query.order_by(text(_PRIORITY_SQL), SampleQueue.created_at.desc())
    else:
        query = query.order_by(SampleQueue.created_at.desc())

    items = query.offset(max(0, offset)).limit(max(1, min(limit, 200))).all()

    result = []
    for item in items:
        latest = (
            db.query(SampleConfirmation)
            .filter(SampleConfirmation.sample_id == item.id)
            .order_by(SampleConfirmation.created_at.desc())
            .first()
        )
        result.append(_serialize(item, latest))
    return result


def get_sample(db: Session, sample_id: int) -> Optional[Dict]:
    item = db.query(SampleQueue).filter(SampleQueue.id == sample_id).first()
    if item is None:
        return None
    latest = (
        db.query(SampleConfirmation)
        .filter(SampleConfirmation.sample_id == item.id)
        .order_by(SampleConfirmation.created_at.desc())
        .first()
    )
    return _serialize(item, latest)


def confirm(
    db: Session,
    sample_id: int,
    action: str,
    final_label: Optional[str] = None,
    user_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> Dict:
    """提交复核结论。

    action:
        adopt    采纳模型预标注（有 VLM 结果则优先采纳 VLM，否则取 CNN top1）
        correct  人工修正为指定标签
        reject   图像不合格或无法判断，不入训练集
    """
    item = db.query(SampleQueue).filter(SampleQueue.id == sample_id).first()
    if item is None:
        raise LookupError(f"样本不存在: {sample_id}")
    if item.status != SampleStatus.pending:
        raise ValueError(
            f"样本 {sample_id} 已复核（当前状态 "
            f"{item.status.value if hasattr(item.status, 'value') else item.status}），不可重复提交"
        )

    if action == "adopt":
        chosen = item.vlm_pred or item.cnn_top1
        if not chosen:
            raise ValueError("该样本没有可采纳的预标注，请改用 correct 指定标签")
        if chosen not in VALID_LABELS:
            raise ValueError(f"预标注 {chosen!r} 不在已知类别内，请改用 correct 指定标签")
        points = MIN_REVIEW_POINTS
        item.status = SampleStatus.confirmed

    elif action == "correct":
        if not final_label:
            raise ValueError("correct 必须提供 final_label")
        if final_label not in VALID_LABELS:
            raise ValueError(
                f"标签 {final_label!r} 不在已知类别内。"
                f"若确属已知类别之外的新病害，请选 {UNKNOWN_LABEL!r}"
            )
        chosen = final_label
        points = CORRECT_REWARD_POINTS
        item.status = SampleStatus.confirmed

    elif action == "reject":
        chosen = None
        points = 0
        item.status = SampleStatus.rejected

    else:
        raise ValueError(f"未知操作: {action}（应为 adopt / correct / reject）")

    record = SampleConfirmation(
        sample_id=item.id,
        final_label=chosen,
        confirmed_by=user_id,
        confirm_source=action,
        points=points,
        notes=notes,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "sample_id": item.id,
        "status": item.status.value if hasattr(item.status, "value") else item.status,
        "final_label": chosen,
        "points": points,
        "confirmation_id": record.id,
    }


def queue_stats(db: Session) -> Dict:
    counts = {s.value: 0 for s in SampleStatus}
    for status, n in db.query(SampleQueue.status, func.count(SampleQueue.id)).group_by(
        SampleQueue.status
    ).all():
        counts[status.value if hasattr(status, "value") else status] = n

    reasons: Dict[str, int] = {}
    for (reason,) in db.query(SampleQueue.trigger_reason).all():
        for r in (reason or "").split("|"):
            if r:
                reasons[r] = reasons.get(r, 0) + 1

    total_points = db.query(func.coalesce(func.sum(SampleConfirmation.points), 0)).scalar() or 0
    confirmed = db.query(SampleConfirmation).count()
    # 已确认中人工修正的比例 —— 这个数字越大，说明模型越需要这批数据
    corrected = db.query(SampleConfirmation).filter(
        SampleConfirmation.confirm_source == "correct"
    ).count()

    return {
        "counts": counts,
        "by_trigger_reason": reasons,
        "confirmations": confirmed,
        "corrected_ratio": round(corrected / confirmed, 4) if confirmed else None,
        "total_points": int(total_points),
        "training_ready_labels": db.query(SampleConfirmation)
        .filter(SampleConfirmation.final_label.isnot(None)).count(),
    }
