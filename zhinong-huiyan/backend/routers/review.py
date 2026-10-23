"""
数据飞轮路由

/review/queue            待复核队列（分歧样本优先）
/review/queue/{id}       单条详情
/review/queue/{id}/confirm  提交复核结论
/review/stats            队列统计
/review/labels           可选标签（复核端下拉用）
/review/versions         模型版本列表
/review/eval-runs        评测记录
/review/gate             手动触发一次门禁
"""
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from database import get_db
from flywheel import gate, review
from labels import DISEASE_CLASSES, SEVERITY_CLASSES, UNKNOWN_LABEL
from models import User
from routers.auth import get_current_user

router = APIRouter()


@router.get("/labels")
async def valid_labels():
    """复核端下拉与"新病害"选项"""
    return {
        "diseases": DISEASE_CLASSES,
        "severities": SEVERITY_CLASSES,
        "unknown": UNKNOWN_LABEL,
    }


@router.get("/queue")
async def get_queue(
    status: str = Query("pending", pattern="^(pending|confirmed|rejected|all)$"),
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """复核队列。pending 时按触发原因排序，CNN/VLM 分歧的排最前。"""
    return review.list_queue(db, status=status, limit=limit, offset=offset)


@router.get("/queue/{sample_id}")
async def get_sample(
    sample_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = review.get_sample(db, sample_id)
    if item is None:
        raise HTTPException(status_code=404, detail="样本不存在")
    return item


@router.post("/queue/{sample_id}/confirm")
async def confirm_sample(
    sample_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """提交复核结论：adopt 采纳预标注 / correct 修正标签 / reject 剔除"""
    action = (payload or {}).get("action")
    if action not in ("adopt", "correct", "reject"):
        raise HTTPException(status_code=400, detail="action 必须是 adopt / correct / reject")

    try:
        return review.confirm(
            db,
            sample_id=sample_id,
            action=action,
            final_label=payload.get("final_label"),
            user_id=current_user.id,
            notes=payload.get("notes"),
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stats")
async def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """队列统计。corrected_ratio 越大，说明模型越需要这批数据。"""
    return review.queue_stats(db)


@router.get("/versions")
async def get_versions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return gate.list_versions(db)


@router.get("/eval-runs")
async def get_eval_runs(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return gate.list_eval_runs(db, limit=limit)


@router.post("/gate")
async def run_gate_endpoint(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """手动跑一次评测门禁。

    会加载两个权重并在整个评测集上推理，耗时以分钟计，因此放进线程池。
    """
    candidate = payload.get("candidate_weights")
    tag = payload.get("candidate_tag")
    dataset = payload.get("dataset")
    if not (candidate and tag and dataset):
        raise HTTPException(status_code=400, detail="需要 candidate_weights / candidate_tag / dataset")

    try:
        return await run_in_threadpool(
            gate.run_gate, db, candidate, tag, dataset,
            payload.get("base_version"), float(payload.get("tolerance", gate.DEFAULT_TOLERANCE)),
            bool(payload.get("allow_demo", False)),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"门禁执行失败: {type(e).__name__}: {e}")
