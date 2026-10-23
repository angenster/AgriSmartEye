"""
诊断 Agent 路由

/agent/diagnose          上传图像触发一次完整诊断（同步）
/agent/diagnose/stream   同一流程，逐步推送 SSE 事件（start/step/report/done）
/agent/runs              列出历史运行
/agent/runs/{run_id}     查看某次运行的报告与完整思考轨迹
"""
import asyncio
import json
import os
import threading
import uuid
from typing import Dict, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from agent.loop import run_agent, serialize_step
from agent.planner import StepRecord
from agent.tools import REGISTRY
from database import SessionLocal, get_db
from models import AgentRun, AgentStep, User
from routers.auth import get_current_user

router = APIRouter()


async def _save_upload(file: UploadFile) -> str:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传有效的图像文件")

    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    upload_dir = "uploads/agent"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{uuid.uuid4().hex}{ext}")
    with open(file_path, "wb") as f:
        f.write(await file.read())
    return file_path


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
    file_path = await _save_upload(file)

    result = await run_in_threadpool(
        run_agent, db, file_path, current_user.id, field_id, "upload"
    )
    if result.get("status") == "failed" and not result.get("steps"):
        raise HTTPException(status_code=503, detail=result.get("error") or "Agent 运行失败")
    return result


def _sse(event: str, data: Dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/diagnose/stream")
async def diagnose_stream(
    file: UploadFile = File(...),
    field_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
):
    """与 /diagnose 相同的诊断流程，但把每一步实时推给前端。

    Agent 循环是同步阻塞的，放在后台线程跑；每完成一步通过 on_step 回调
    投递到 asyncio 队列，由 SSE 生成器按序下发。数据库 session 在后台线程
    内独立创建，不与请求的依赖 session 跨线程共用。
    """
    file_path = await _save_upload(file)
    user_id = current_user.id
    loop = asyncio.get_running_loop()
    events: asyncio.Queue = asyncio.Queue()

    def emit(event: str, data: Dict) -> None:
        loop.call_soon_threadsafe(events.put_nowait, {"event": event, "data": data})

    def on_step(record: StepRecord) -> None:
        emit("step", serialize_step(record))

    def worker() -> None:
        db = SessionLocal()
        try:
            result = run_agent(db, file_path, user_id, field_id, "upload_stream",
                               on_step=on_step)
            emit("report", result)
        except Exception as e:  # noqa: BLE001 - 失败也要让前端收到明确终态
            emit("error", {"message": f"{type(e).__name__}: {e}"})
        finally:
            db.close()
            emit("done", {})

    threading.Thread(target=worker, daemon=True).start()

    async def event_stream():
        yield _sse("start", {"image_path": file_path})
        while True:
            item = await events.get()
            yield _sse(item["event"], item["data"])
            if item["event"] == "done":
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 关闭 nginx 缓冲，否则事件会被攒着不发
        },
    )


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
