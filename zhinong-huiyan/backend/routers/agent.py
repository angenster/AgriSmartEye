"""
诊断 Agent 路由

/agent/diagnose        上传图像触发一次完整诊断
/agent/runs            列出历史运行
/agent/runs/{run_id}   查看某次运行的报告与完整思考轨迹
"""
import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from agent.loop import run_agent
from agent.tools import REGISTRY
from database import get_db
from models import AgentRun, AgentStep, User
from routers.auth import get_current_user

router = APIRouter()


@router.post("/diagnose")
async def diagnose(
    file: UploadFile = File(...),
    field_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传图像并跑一次诊断 Agent。

    Agent 会自主决定是否升级 VLM、查证知识库、转人工，全过程落库到 agent_runs/steps。
    推理与循环都是阻塞调用，整体丢进线程池执行，避免堵住事件循环。
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传有效的图像文件")

    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    upload_dir = "uploads/agent"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{uuid.uuid4().hex}{ext}")
    with open(file_path, "wb") as f:
        f.write(await file.read())

    result = await run_in_threadpool(
        run_agent, db, file_path, current_user.id, field_id, "upload"
    )
    if result.get("status") == "failed" and not result.get("steps"):
        raise HTTPException(status_code=503, detail=result.get("error") or "Agent 运行失败")
    return result


@router.get("/tools")
async def list_tools():
    """列出 Agent 的白名单工具，便于对照与调试"""
    return [
        {"name": s.name, "description": s.description, "required": s.required,
         "parameters": list(s.parameters)}
        for s in REGISTRY.values()
    ]


@router.get("/runs")
async def list_runs(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出当前用户的诊断运行"""
    runs = (
        db.query(AgentRun)
        .filter(AgentRun.user_id == current_user.id)
        .order_by(AgentRun.created_at.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    return [
        {
            "run_id": r.id,
            "status": r.status.value if hasattr(r.status, "value") else r.status,
            "trigger": r.trigger,
            "image_path": r.image_path,
            "steps_used": r.steps_used,
            "vlm_calls": r.vlm_calls,
            "llm_tokens": r.llm_tokens,
            "total_latency_ms": r.total_latency_ms,
            "planner": r.planner,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "disease": ((r.report_json or {}).get("disease") or {}).get("name"),
            "needs_human": (r.report_json or {}).get("needs_human"),
        }
        for r in runs
    ]


@router.get("/runs/{run_id}")
async def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查看某次运行的报告与完整思考轨迹"""
    run = (
        db.query(AgentRun)
        .filter(AgentRun.id == run_id, AgentRun.user_id == current_user.id)
        .first()
    )
    if run is None:
        raise HTTPException(status_code=404, detail="运行记录不存在")

    steps = (
        db.query(AgentStep)
        .filter(AgentStep.run_id == run_id)
        .order_by(AgentStep.step_no)
        .all()
    )

    return {
        "run_id": run.id,
        "status": run.status.value if hasattr(run.status, "value") else run.status,
        "planner": run.planner,
        "steps_used": run.steps_used,
        "vlm_calls": run.vlm_calls,
        "llm_tokens": run.llm_tokens,
        "total_latency_ms": run.total_latency_ms,
        "error": run.error,
        "report": run.report_json,
        "steps": [
            {
                "step_no": s.step_no,
                "step_id": s.id,
                "thought": s.thought,
                "tool_name": s.tool_name,
                "tool_args": s.tool_args_json,
                "tool_result": s.tool_result_json,
                "error": s.error,
                "latency_ms": s.latency_ms,
            }
            for s in steps
        ],
    }
