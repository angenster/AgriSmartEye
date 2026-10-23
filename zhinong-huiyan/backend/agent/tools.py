"""
Agent 工具层 —— Agent 唯一的能力出口，白名单制。

约定：
  所有工具返回统一契约，绝不抛异常给循环，也绝不静默吞掉错误：
      {"ok": True,  "data": {...}}
      {"ok": False, "error": {"code": str, "message": str}}

  这样 Agent（或规则仲裁）总能明确看到某一步失败的原因，并决定重试或降级。
  数据源尚未就绪的能力（RAG 索引、农药登记库、VLM 密钥）返回带明确 code 的
  错误对象，而不是伪装成空结果 —— 否则会把"没查"误当成"查过且没有"。
"""
import base64
import json
import mimetypes
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from agent import config
from models import DetectionRecord, Field, OperationRecord
from services.model_service import model_service, ModelNotAvailable


# ---------------------------------------------------------------- 上下文与规格

@dataclass
class ToolContext:
    """一次 Agent 运行期间工具可访问的上下文"""
    db: Session
    image_path: str
    user_id: Optional[int] = None
    field_id: Optional[int] = None
    # 运行时累计，供报告的成本字段使用
    counters: Dict[str, Any] = field(default_factory=dict)

    def bump(self, key: str, amount: int = 1) -> None:
        self.counters[key] = self.counters.get(key, 0) + amount


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Dict[str, Any]]   # 形如 {"image_path": {"type": "string", "description": ...}}
    required: List[str]
    fn: Callable[..., Dict]

    def json_schema(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    k: {kk: vv for kk, vv in v.items() if kk != "required"}
                    for k, v in self.parameters.items()
                },
                "required": self.required,
            },
        }


class ToolError(Exception):
    """工具内部抛出的、可安全回给 Agent 的错误"""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def ok(data: Dict) -> Dict:
    return {"ok": True, "data": data}


def err(code: str, message: str) -> Dict:
    return {"ok": False, "error": {"code": code, "message": message}}


# ---------------------------------------------------------------- 参数校验

_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
}


def validate_args(spec: ToolSpec, args: Dict) -> Optional[str]:
    """返回错误说明；通过则返回 None。不引入 jsonschema 依赖，手写足够。"""
    if not isinstance(args, dict):
        return "参数必须是 JSON 对象"

    for name in spec.required:
        if name not in args or args[name] is None:
            return f"缺少必填参数: {name}"

    for name, value in args.items():
        param = spec.parameters.get(name)
        if param is None:
            return f"未知参数: {name}"
        if value is None:
            continue
        checker = _TYPE_CHECKS.get(param.get("type", "string"))
        if checker and not checker(value):
            return f"参数 {name} 类型应为 {param.get('type')}"

    return None


# ---------------------------------------------------------------- 工具实现

def _tool_run_cnn_detect(ctx: ToolContext, image_path: Optional[str] = None) -> Dict:
    """CNN 一线快筛。复用进程内单例推理引擎，并把结果落库以获得稳定证据编号。"""
    path = image_path or ctx.image_path
    if not path or not os.path.exists(path):
        raise ToolError("image_not_found", f"图像不存在: {path!r}")

    try:
        result = model_service.predict(path)
    except ModelNotAvailable as e:
        raise ToolError("model_unavailable", str(e))

    record = DetectionRecord(
        user_id=ctx.user_id,
        field_id=ctx.field_id,
        image_path=path,
        crop_type=result["crop"]["name"],
        disease_name=result["disease"]["name"],
        confidence=result["disease"]["confidence"],
        severity=result["severity"]["name"],
        bbox=None,
        model_version=model_service.model_version,
        inference_time=result["inference_time_ms"],
    )
    ctx.db.add(record)
    ctx.db.commit()
    ctx.db.refresh(record)

    topk = result["disease"]["topk"]
    return ok({
        "detection_id": record.id,
        "crop": result["crop"]["name"],
        "crop_confidence": result["crop"]["confidence"],
        "disease": result["disease"]["name"],
        "confidence": result["disease"]["confidence"],
        "severity": result["severity"]["name"],
        "severity_confidence": result["severity"]["confidence"],
        "topk": topk,
        "margin": round(topk[0]["confidence"] - topk[1]["confidence"], 4) if len(topk) > 1 else topk[0]["confidence"],
        "latency_ms": result["inference_time_ms"],
        "model_version": model_service.model_version,
        "is_demo": result["is_demo"],
    })


_VLM_SYSTEM_PROMPT = """你是热带作物病虫害识别专家。你要从给定的候选类别中选出最可能的一项，并给出判断依据。

规则：
- 只能从下面列出的类别中选择，不得自创名称
- 若图像无法判断或不属于任何一类，disease 填 "其他/未知"，并把 confidence 设为很低的值
- 必须给出可核对的视觉依据（rationale），描述你看到的病斑形态、颜色、分布等
- 只输出 JSON，不要输出任何其他文字"""

_VLM_USER_TEMPLATE = """请诊断这张作物叶片/果实图像。

可选病害类别：
{labels}

可选严重程度：轻度 / 中度 / 重度

按以下 JSON 结构输出：
{{
  "disease": "类别名",
  "severity": "轻度|中度|重度",
  "confidence": 0.0~1.0 之间的小数,
  "rationale": "你观察到的视觉依据",
  "alternatives": [{{"name": "类别名", "confidence": 0.0}}]
}}"""


def _tool_escalate_vlm(ctx: ToolContext, image_path: Optional[str] = None,
                       reason: str = "", question: Optional[str] = None) -> Dict:
    """升级到云端 VLM 精判。未配置密钥时返回结构化错误，由上层决定降级。"""
    from labels import DISEASE_CLASSES

    if not config.vlm_configured():
        raise ToolError(
            "vlm_not_configured",
            "未配置 VLM_API_KEY，无法升级多模态模型。"
            "请设置 VLM_API_KEY / VLM_BASE_URL / VLM_MODEL 后重试。",
        )

    path = image_path or ctx.image_path
    if not path or not os.path.exists(path):
        raise ToolError("image_not_found", f"图像不存在: {path!r}")

    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    user_text = _VLM_USER_TEMPLATE.format(labels="、".join(DISEASE_CLASSES))
    if question:
        user_text += f"\n\n附加问题：{question}"

    payload = {
        "model": config.VLM_MODEL,
        "messages": [
            {"role": "system", "content": _VLM_SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ]},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.0,
    }

    started = time.time()
    try:
        resp = httpx.post(
            f"{config.VLM_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {config.VLM_API_KEY}"},
            json=payload,
            timeout=config.VLM_TIMEOUT_S,
        )
        resp.raise_for_status()
        body = resp.json()
    except httpx.TimeoutException:
        raise ToolError("vlm_timeout", f"VLM 调用超时（>{config.VLM_TIMEOUT_S}s）")
    except httpx.HTTPStatusError as e:
        raise ToolError("vlm_http_error", f"VLM 返回 {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:  # noqa: BLE001
        raise ToolError("vlm_error", f"{type(e).__name__}: {e}")

    latency_ms = round((time.time() - started) * 1000, 2)
    try:
        parsed = json.loads(body["choices"][0]["message"]["content"])
    except Exception as e:  # noqa: BLE001
        raise ToolError("vlm_bad_response", f"VLM 输出无法解析为 JSON: {type(e).__name__}: {e}")

    usage = body.get("usage") or {}
    ctx.bump("vlm_calls")
    ctx.bump("llm_tokens", int(usage.get("total_tokens") or 0))

    confidence = float(parsed.get("confidence") or 0.0)
    return ok({
        "disease": parsed.get("disease"),
        "severity": parsed.get("severity"),
        "confidence": round(max(0.0, min(1.0, confidence)), 4),
        "rationale": parsed.get("rationale"),
        "alternatives": parsed.get("alternatives") or [],
        "reason": reason,
        "latency_ms": latency_ms,
        "cost": {"total_tokens": usage.get("total_tokens"), "model": config.VLM_MODEL},
    })


def _tool_search_knowledge(ctx: ToolContext, query: str, top_k: int = 5) -> Dict:
    """检索农技知识。

    走 rag.retriever 的混合检索（FTS5 关键词 + 向量 → RRF 融合 → 重排）。
    索引里没有内容或嵌入模型不可用时，如实回报原因，而不是伪装成"查过且没有"。
    """
    top_k = max(1, min(int(top_k or 5), 20))

    try:
        from rag import retriever
        result = retriever.search(query, top_k=top_k)
    except Exception as e:  # noqa: BLE001 - RAG 基建故障不应让 Agent 崩掉
        raise ToolError(
            "rag_unavailable",
            f"检索子系统不可用：{type(e).__name__}: {e}。"
            "请确认已执行 `python -m rag.indexer` 建索引，且 sqlite-vec 与嵌入模型可用。",
        )

    chunks = result.get("chunks") or []
    if not chunks:
        raise ToolError(
            "empty_result",
            f"知识库未命中「{query}」（检索模式 {result.get('mode')}，"
            f"FTS 命中 {result.get('fts_hits')} 条、向量命中 {result.get('vector_hits')} 条）。",
        )

    return ok({
        "query": query,
        "chunks": chunks,
        "retrieval": {
            "mode": result.get("mode"),
            "vector_ok": result.get("vector_ok"),
            "rerank_ok": result.get("rerank_ok"),
            "embedder_error": result.get("embedder_error"),
        },
    })


def _tool_get_field_context(ctx: ToolContext, field_id: Optional[int] = None) -> Dict:
    """取地块信息与近期作业/检测史，供 Agent 结合上下文判断。"""
    fid = field_id if field_id is not None else ctx.field_id
    if fid is None:
        raise ToolError("field_not_specified", "未提供 field_id，且本次运行未绑定地块")

    field_row = ctx.db.query(Field).filter(Field.id == fid).first()
    if field_row is None:
        raise ToolError("field_not_found", f"地块不存在: {fid}")

    ops = (
        ctx.db.query(OperationRecord)
        .filter(OperationRecord.field_id == fid)
        .order_by(OperationRecord.created_at.desc())
        .limit(10)
        .all()
    )
    dets = (
        ctx.db.query(DetectionRecord)
        .filter(DetectionRecord.field_id == fid)
        .order_by(DetectionRecord.created_at.desc())
        .limit(10)
        .all()
    )

    return ok({
        "field": {
            "id": field_row.id,
            "name": field_row.name,
            "crop_type": field_row.crop_type,
            "area": field_row.area,
            "location": field_row.location,
            "status": field_row.status.value if hasattr(field_row.status, "value") else field_row.status,
            "last_check": field_row.last_check.isoformat() if field_row.last_check else None,
        },
        "recent_operations": [
            {"type": o.type.value if hasattr(o.type, "value") else o.type,
             "content": o.content,
             "created_at": o.created_at.isoformat() if o.created_at else None}
            for o in ops
        ],
        "recent_detections": [
            {"id": d.id, "disease": d.disease_name, "severity": d.severity,
             "confidence": d.confidence,
             "created_at": d.created_at.isoformat() if d.created_at else None}
            for d in dets
        ],
    })


def _tool_query_pesticide(ctx: ToolContext, disease_name: str, crop_type: Optional[str] = None) -> Dict:
    """查询登记农药。数据源（农药登记信息）尚未整理入库，故明确报不可用。

    红线 #3：药品名称与剂量只能来自检索结果，禁止模型生成。
    因此在数据源就绪前，本工具宁可失败也不返回任何内容。
    """
    raise ToolError(
        "pesticide_registry_unavailable",
        "农药登记库尚未建立（P2 落地）。按项目红线，药品与剂量不得由模型生成，"
        "故本次不返回任何用药建议。",
    )


def _tool_request_human_review(ctx: ToolContext, reason: str, report_draft: Optional[Dict] = None) -> Dict:
    """把本次运行转人工复核。P1 阶段以 agent_runs.status 作为工单载体，
    完整复核队列（sample_queue + ReviewQueue 前端）属于 P3。"""
    if not reason:
        raise ToolError("missing_reason", "转人工必须说明原因")
    ctx.counters["human_review_requested"] = True
    ctx.counters["human_review_reason"] = reason
    return ok({
        "ticket_id": ctx.counters.get("run_id"),
        "reason": reason,
        "queue": "agent_runs.status=needs_human",
        "note": "完整复核队列（sample_queue + 复核端）属于 P3，当前以本次运行记录作为工单",
    })


# ---------------------------------------------------------------- 注册表

def _build_registry() -> Dict[str, ToolSpec]:
    specs = [
        ToolSpec(
            name="run_cnn_detect",
            description="用轻量化 CNN 对图像做一线快筛，返回作物/病害/严重度/置信度与 top5 候选。速度快、成本低。",
            parameters={
                "image_path": {"type": "string", "description": "图像路径，缺省用本次运行的图像"},
            },
            required=[],
            fn=_tool_run_cnn_detect,
        ),
        ToolSpec(
            name="escalate_vlm",
            description="升级到云端多模态大模型精判，用于 CNN 低置信或 CNN/VLM 分歧的样本。较慢、有成本，调用时必须在 reason 说明升级理由。",
            parameters={
                "image_path": {"type": "string", "description": "图像路径，缺省用本次运行的图像"},
                "reason": {"type": "string", "description": "为什么需要升级（必填）"},
                "question": {"type": "string", "description": "可选的补充问题"},
            },
            required=["reason"],
            fn=_tool_escalate_vlm,
        ),
        ToolSpec(
            name="search_knowledge",
            description="检索农技知识库，返回带 chunk_id 的知识片段，用于核对症状与防治方法。报告中的引用必须来自这里。",
            parameters={
                "query": {"type": "string", "description": "检索关键词，通常是病害名或症状"},
                "top_k": {"type": "integer", "description": "返回条数，默认 5"},
            },
            required=["query"],
            fn=_tool_search_knowledge,
        ),
        ToolSpec(
            name="get_field_context",
            description="获取地块信息、近期作业记录与历史检测结果，用于结合农事上下文判断。",
            parameters={
                "field_id": {"type": "integer", "description": "地块 id，缺省用本次运行绑定的地块"},
            },
            required=[],
            fn=_tool_get_field_context,
        ),
        ToolSpec(
            name="query_pesticide",
            description="查询某病害在某作物上的登记农药（名称/剂型/剂量/安全间隔期）。药品只能来自本工具，禁止自行生成。",
            parameters={
                "disease_name": {"type": "string", "description": "病害名称"},
                "crop_type": {"type": "string", "description": "作物名称"},
            },
            required=["disease_name"],
            fn=_tool_query_pesticide,
        ),
        ToolSpec(
            name="request_human_review",
            description="当证据矛盾、或属于用药安全高风险情形时，终止自动诊断并转人工复核。",
            parameters={
                "reason": {"type": "string", "description": "转人工的原因"},
                "report_draft": {"type": "object", "description": "当前报告草稿"},
            },
            required=["reason"],
            fn=_tool_request_human_review,
        ),
    ]
    return {s.name: s for s in specs}


REGISTRY: Dict[str, ToolSpec] = _build_registry()

# 供 LLM planner 使用的 OpenAI function calling 格式
TOOL_SCHEMAS: List[Dict] = [s.json_schema() for s in REGISTRY.values()]


def dispatch(name: str, args: Dict, ctx: ToolContext) -> Dict:
    """白名单分发：未注册的工具一律拒绝；工具异常统一转成错误对象。"""
    spec = REGISTRY.get(name)
    if spec is None:
        return err("unknown_tool", f"工具 {name!r} 不在白名单内，可用工具: {sorted(REGISTRY)}")

    problem = validate_args(spec, args)
    if problem:
        return err("invalid_args", problem)

    try:
        return spec.fn(ctx, **args)
    except ToolError as e:
        return err(e.code, e.message)
    except TypeError as e:
        # 通常是参数名不匹配
        return err("invalid_args", f"调用 {name} 失败: {e}")
    except Exception as e:  # noqa: BLE001 - 兜底：任何未预期异常都变成可读错误，不让循环崩掉
        return err("tool_exception", f"{type(e).__name__}: {e}")
