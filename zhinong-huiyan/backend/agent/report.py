"""
诊断报告组装与证据核对。

两条硬约束（方案 §4.4 与红线 #3）：
  1. 报告中每条判断都必须挂结构化证据，引用必须能在库里查到，
     否则报告判为无效（verify_evidence 返回 ok=False）。
  2. 药品名称与剂量只能来自 query_pesticide / search_knowledge 的返回，
     绝不使用模型自由生成的内容。数据源不可用时宁可为空。
"""
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from agent.config import HIGH_VALUE_CROPS
from agent.planner import StepRecord, last_ok
from labels import HEALTHY_LABEL, SEVERITY_TRAINED

DISCLAIMER = "本报告由 AI 生成，仅供参考，请遵循当地农技部门指导施药。"

# 证据引用格式： "<表名>.id=<整数>"，例如 detection_records.id=12
_REF_PATTERN = re.compile(r"^(?P<table>[a-z_]+)\.id=(?P<pk>\d+)$")

# 允许被引用的表 —— 白名单，防止模型引用不存在的证据来源
_REF_TABLES = {
    "detection_records",
    "pest_info",
    "agent_steps",
    "knowledge_chunks",   # P2 落地后启用
}


def _cnn_evidence(cnn: Dict) -> Dict:
    return {
        "type": "cnn",
        "ref": f"detection_records.id={cnn.get('detection_id')}",
        "summary": (f"CNN 判为「{cnn.get('disease')}」（置信度 {cnn.get('confidence')}，"
                    f"当前 top1-top2 间距 {cnn.get('margin')}）"),
    }


def _vlm_evidence(vlm: Dict, step_id: Optional[int]) -> Dict:
    ref = f"agent_steps.id={step_id}" if step_id is not None else "agent_steps.id=0"
    return {
        "type": "vlm",
        "ref": ref,
        "summary": (f"VLM 判为「{vlm.get('disease')}」（置信度 {vlm.get('confidence')}）。"
                    f"依据：{vlm.get('rationale') or '未提供'}"),
    }


def _rag_evidence(chunk: Dict) -> Dict:
    """证据引用必须指向真实存在的表（knowledge_chunks），
    source 只作为溯源信息单独携带 —— 早先把它当表名拼进 ref，
    会让每一条 RAG 引用都通不过核对。"""
    return {
        "type": "rag",
        "ref": f"knowledge_chunks.id={chunk.get('chunk_id')}",
        "quote": (chunk.get("text") or "")[:200],
        "source": chunk.get("source"),
        "title": chunk.get("title"),
        "reviewed": chunk.get("reviewed"),
    }


def build_report(
    history: List[StepRecord],
    ctx,
    run_id: Optional[int],
    image_path: str,
    truncated: bool = False,
) -> Dict:
    """把工具轨迹汇总为 DiagnosticReport。"""
    cnn = last_ok(history, "run_cnn_detect") or {}
    vlm = last_ok(history, "escalate_vlm")
    knowledge = last_ok(history, "search_knowledge")
    field_ctx = last_ok(history, "get_field_context")
    pesticides = last_ok(history, "query_pesticide")

    # 最终病名：VLM 优先（它是为解决 CNN 不确定而升级的），否则用 CNN
    if vlm and vlm.get("disease"):
        disease_name = vlm["disease"]
        disease_conf = vlm.get("confidence")
        disease_source = "vlm"
    else:
        disease_name = cnn.get("disease")
        disease_conf = cnn.get("confidence")
        disease_source = "cnn"

    severity = (vlm or {}).get("severity") or cnn.get("severity")
    severity_conf = (vlm or {}).get("severity_confidence") or cnn.get("severity_confidence")

    # ---- 证据链 ----
    evidence: List[Dict] = []
    if cnn.get("detection_id") is not None:
        evidence.append(_cnn_evidence(cnn))
    if vlm:
        step_id = next((r.step_id for r in reversed(history)
                        if r.tool_name == "escalate_vlm" and r.result.get("ok")), None)
        evidence.append(_vlm_evidence(vlm, step_id))
    for chunk in (knowledge or {}).get("chunks", []):
        evidence.append(_rag_evidence(chunk))

    # ---- 治疗方案：一律来自检索，绝不生成 ----
    # 只采用与最终诊断病名一致的知识条目。检索返回的是一个候选集合
    # （含同科近缘病、同作物的其他病），若把它们的防治措施合并，
    # 就等于把别的病的建议开给了当前病。
    treatment_steps: List[str] = []
    treatment_chunks: List[Dict] = []
    if knowledge:
        treatment_chunks = [
            c for c in knowledge.get("chunks", []) if (c.get("ref_id") or "") == disease_name
        ]
        for chunk in treatment_chunks:
            for line in (chunk.get("text") or "").splitlines():
                if line.startswith("预防：") or line.startswith("防治："):
                    treatment_steps.extend(
                        s.strip() for s in line.split("：", 1)[1].split("；") if s.strip()
                    )
    medicines = []
    if pesticides:
        for item in pesticides.get("pesticides", []):
            medicines.append({
                "name": item.get("name"),
                "dosage": item.get("dosage"),
                "safe_interval_days": item.get("safe_interval_days"),
                "source_chunk": item.get("source_chunk"),
            })

    if disease_name == HEALTHY_LABEL:
        treatment_steps = []
        medicines = []

    # ---- 是否转人工 ----
    review_step = next((r for r in reversed(history) if r.tool_name == "request_human_review"), None)
    needs_human = bool(review_step and review_step.result.get("ok"))
    human_reason = (review_step.tool_args.get("reason") if review_step else None)

    # 兜底：证据不足或缺乏知识支撑时也必须转人工
    if not knowledge and not needs_human:
        needs_human = True
        human_reason = human_reason or "知识库无可用证据，无法给出有依据的防治方案"

    candidates = [
        {"name": t["name"], "confidence": t["confidence"]}
        for t in (cnn.get("topk") or [])[:5]
    ]

    report = {
        "report_id": str(uuid.uuid4()),
        "run_id": run_id,
        "field_id": ctx.field_id,
        "image_path": image_path,
        "crop": {
            "name": cnn.get("crop"),
            "confidence": cnn.get("crop_confidence"),
            "source": "cnn",
        },
        "disease": {
            "name": disease_name,
            "confidence": disease_conf,
            "source": disease_source,
            "candidates": candidates,
        },
        "severity": {
            "level": severity,
            "confidence": severity_conf,
            "basis": ("未训练严重度头（公开数据无严重度标注），本次不评估" if not SEVERITY_TRAINED
                      else (f"VLM 目视估计（{vlm.get('rationale')}）" if vlm and vlm.get("rationale")
                            else "CNN 严重程度头输出")),
        },
        "evidence": evidence,
        "treatment": {
            "steps": treatment_steps,
            "medicines": medicines,
            "source_chunks": [c.get("chunk_id") for c in treatment_chunks],
            "note": (
                "未提供具体药剂：登记农药数据源尚未建立，按项目红线不生成药品与剂量"
                if knowledge else
                "无知识库支撑，未给出防治措施"
            ),
        },
        "needs_human": needs_human,
        "human_review_reason": human_reason,
        "truncated": truncated,
        "knowledge_available": bool(knowledge),
        "field_context": field_ctx,
        "disclaimer": DISCLAIMER,
        "cost": {
            "vlm_calls": ctx.counters.get("vlm_calls", 0),
            "llm_tokens": ctx.counters.get("llm_tokens", 0),
        },
    }
    return report


def verify_evidence(report: Dict, db: Session) -> Tuple[bool, List[str]]:
    """逐条核对证据引用是否真实存在于库中。

    引用不存在 → 报告无效。这是"证据可核对"的落地方式：
    不依赖模型自觉，而是程序逐条查库。
    """
    problems: List[str] = []
    evidence = report.get("evidence") or []
    if not evidence:
        problems.append("报告没有任何证据条目")

    for item in evidence:
        ref = item.get("ref") or ""
        m = _REF_PATTERN.match(ref)
        if not m:
            problems.append(f"证据引用格式非法: {ref!r}")
            continue
        table, pk = m.group("table"), int(m.group("pk"))
        if table not in _REF_TABLES:
            problems.append(f"证据引用了不允许的来源表: {table}")
            continue
        if not _row_exists(db, table, pk):
            problems.append(f"证据引用不存在: {ref}")

    return (not problems), problems


def _row_exists(db: Session, table: str, pk: int) -> bool:
    from sqlalchemy import text

    try:
        row = db.execute(
            text(f"SELECT 1 FROM {table} WHERE id = :pk LIMIT 1"), {"pk": pk}
        ).first()
        return row is not None
    except Exception:  # noqa: BLE001 - 表不存在（如 P2 的 knowledge_chunks）视为引用无效
        return False
