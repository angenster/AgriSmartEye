"""
ReAct 循环 —— Agent 的主控。

结构（与方案 §5.4 一致）：
    观察历史 → planner 决定下一步 → 白名单分发执行 → 记录轨迹 → 回到观察

关键约束：
  - 步数预算 MAX_STEPS，超限则输出当前最佳草稿并标记 truncated
  - 每一步都落库到 agent_steps，前端据此渲染思考过程时间线
  - 任何异常都收敛为 failed 状态并保留已完成步骤，不让请求 500 掉
"""
import time
import traceback
from typing import Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from agent import config
from agent.planner import StepRecord, get_planner, last_ok
from agent.report import build_report, verify_evidence
from agent.tools import ToolContext, dispatch
from models import AgentRun, AgentRunStatus, AgentStep


def run_agent(
    db: Session,
    image_path: str,
    user_id: Optional[int] = None,
    field_id: Optional[int] = None,
    trigger: str = "upload",
    on_step: Optional[Callable[[StepRecord], None]] = None,
) -> Dict:
    """跑完一次诊断 Agent，返回包含报告与轨迹的结果字典。

    on_step 回调用于 SSE 流式推送，每完成一步调用一次。
    """
    started = time.time()

    run = AgentRun(
        user_id=user_id,
        field_id=field_id,
        trigger=trigger,
        image_path=image_path,
        status=AgentRunStatus.running,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    ctx = ToolContext(db=db, image_path=image_path, user_id=user_id, field_id=field_id)
    ctx.counters["run_id"] = run.id

    planner = get_planner()
    run.planner = planner.name
    db.commit()

    history: List[StepRecord] = []
    truncated = False

    try:
        for step_no in range(1, config.MAX_STEPS + 1):
            decision = planner.decide(history, ctx)
            if decision.done:
                break

            step_started = time.time()
            result = dispatch(decision.tool_name, decision.tool_args, ctx)
            step_latency = round((time.time() - step_started) * 1000, 2)

            step_row = AgentStep(
                run_id=run.id,
                step_no=step_no,
                thought=decision.thought,
                tool_name=decision.tool_name,
                tool_args_json=decision.tool_args,
                tool_result_json=result,
                error=None if result.get("ok") else (result.get("error") or {}).get("message"),
                latency_ms=step_latency,
            )
            db.add(step_row)
            db.commit()
            db.refresh(step_row)

            record = StepRecord(
                step_no=step_no,
                thought=decision.thought,
                tool_name=decision.tool_name,
                tool_args=decision.tool_args,
                result=result,
                step_id=step_row.id,
            )
            history.append(record)
            if on_step:
                on_step(record)
        else:
            # for-else：循环自然走完，说明预算耗尽而 planner 仍未判定完成
            truncated = True

    except Exception as e:  # noqa: BLE001 - 兜底，保证 run 有终态
        run.status = AgentRunStatus.failed
        run.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()[:2000]}"
        run.steps_used = len(history)
        run.total_latency_ms = round((time.time() - started) * 1000, 2)
        db.commit()
        return {
            "run_id": run.id,
            "status": run.status.value,
            "error": run.error,
            "steps": _serialize_steps(history),
            "report": None,
            "evidence_valid": False,
            "evidence_problems": ["运行失败，未生成报告"],
        }

    report = build_report(history, ctx, run.id, image_path, truncated=truncated)
    evidence_ok, problems = verify_evidence(report, db)

    # 引用核对不过 → 报告不可信，必须转人工而不是照常输出
    if not evidence_ok:
        report["needs_human"] = True
        report["human_review_reason"] = report.get("human_review_reason") or "证据引用核对未通过"
    report["evidence_valid"] = evidence_ok
    report["evidence_problems"] = problems

    if report["needs_human"]:
        status = AgentRunStatus.needs_human
    elif truncated:
        status = AgentRunStatus.truncated
    else:
        status = AgentRunStatus.done

    run.status = status
    run.steps_used = len(history)
    run.vlm_calls = ctx.counters.get("vlm_calls", 0)
    run.llm_tokens = ctx.counters.get("llm_tokens", 0)
    run.total_latency_ms = round((time.time() - started) * 1000, 2)
    report["cost"]["latency_ms"] = run.total_latency_ms
    run.report_json = report
    db.commit()

    # ---- 数据飞轮：把"模型拿不准"的样本自动送进复核队列 ----
    # 失败不能影响诊断结果本身，因此单独兜底并如实回报
    try:
        from flywheel.trigger import maybe_enqueue

        enqueue_info = maybe_enqueue(
            db,
            image_path=image_path,
            cnn=last_ok(history, "run_cnn_detect") or {},
            vlm=last_ok(history, "escalate_vlm"),
            source="agent_run",
            run_id=run.id,
            field_id=field_id,
        )
    except Exception as e:  # noqa: BLE001
        enqueue_info = {"error": f"{type(e).__name__}: {e}"}

    report["flywheel"] = enqueue_info
    run.report_json = report
    db.commit()

    return {
        "run_id": run.id,
        "status": status.value,
        "planner": run.planner,
        "steps_used": run.steps_used,
        "report": report,
        "evidence_valid": evidence_ok,
        "evidence_problems": problems,
        "flywheel": enqueue_info,
        "steps": _serialize_steps(history),
    }


def serialize_step(record: StepRecord) -> Dict:
    """单步转成前端渲染时间线用的结构（SSE 与最终结果共用同一份字段）"""
    return {
        "step_no": record.step_no,
        "step_id": record.step_id,
        "thought": record.thought,
        "tool_name": record.tool_name,
        "tool_args": record.tool_args,
        "ok": bool(record.result.get("ok")),
        "result": (record.result.get("data") if record.result.get("ok")
                   else record.result.get("error")),
    }


def _serialize_steps(history: List[StepRecord]) -> List[Dict]:
    """把轨迹转成前端渲染时间线用的结构"""
    return [serialize_step(r) for r in history]
