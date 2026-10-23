"""
planner —— 决定 Agent 下一步做什么。

两种实现，接口一致：

  RuleBasedPlanner  确定性规则，严格实现方案 §5.4 的仲裁表。无需任何密钥，
                    是默认实现。注意：方案本就要求仲裁规则"代码层强制，
                    不依赖 Agent 自觉"，因此它同时也是 LLM planner 的安全底座。

  LLMPlanner        OpenAI 兼容的 function calling。设置 LLM_API_KEY 后自动启用，
                    用于让模型自主取舍工具顺序与措辞。
"""
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from agent import config
from agent.tools import TOOL_SCHEMAS
from labels import HEALTHY_LABEL, crop_of_label


@dataclass
class Decision:
    thought: str
    tool_name: Optional[str] = None
    tool_args: Dict[str, Any] = field(default_factory=dict)
    done: bool = False


@dataclass
class StepRecord:
    """循环里的一步，供 planner 回看。step_id 是 agent_steps 落库后的行号，
    用于报告里生成可核对的证据引用。"""
    step_no: int
    thought: str
    tool_name: str
    tool_args: Dict[str, Any]
    result: Dict[str, Any]
    step_id: Optional[int] = None


def last_ok(history: List[StepRecord], tool_name: str) -> Optional[Dict]:
    """取某工具最近一次成功返回的 data"""
    for rec in reversed(history):
        if rec.tool_name == tool_name and rec.result.get("ok"):
            return rec.result.get("data")
    return None


def tried(history: List[StepRecord], tool_name: str) -> bool:
    return any(rec.tool_name == tool_name for rec in history)


class RuleBasedPlanner:
    """确定性仲裁：与方案 §5.4 的表格一一对应。"""

    name = "rule_based"

    def decide(self, history: List[StepRecord], ctx) -> Decision:
        cnn = last_ok(history, "run_cnn_detect")

        # 1) 先跑一线快筛
        if cnn is None:
            if tried(history, "run_cnn_detect"):
                # 上一次失败了，不再空转
                return Decision(thought="CNN 快筛失败，无法继续自动诊断，转人工。",
                                tool_name="request_human_review",
                                tool_args={"reason": "CNN 推理不可用"})
            return Decision(thought="先用轻量化 CNN 做一线快筛。", tool_name="run_cnn_detect")

        confidence = float(cnn.get("confidence") or 0.0)
        margin = float(cnn.get("margin") or 0.0)
        needs_vlm = confidence < config.TAU_LOW or margin < config.MARGIN

        # 2) 双引擎仲裁
        if needs_vlm and not tried(history, "escalate_vlm"):
            if confidence < config.TAU_LOW:
                why = f"CNN 病害置信度 {confidence:.2f} 低于阈值 {config.TAU_LOW}"
            else:
                why = f"CNN top1-top2 间距 {margin:.2f} 小于 {config.MARGIN}，存在混淆"
            return Decision(
                thought=f"{why}，升级多模态模型精判。",
                tool_name="escalate_vlm",
                tool_args={"reason": why},
            )

        if not needs_vlm and confidence >= config.TAU_HIGH:
            pass  # 直接采纳 CNN，跳过 VLM（省成本），继续往下查证

        # 3) 用最终病名查知识库
        vlm = last_ok(history, "escalate_vlm")
        disease = (vlm or {}).get("disease") or cnn.get("disease")
        crop = cnn.get("crop")

        if not tried(history, "search_knowledge"):
            return Decision(
                thought=f"用「{disease}」检索农技知识，核对症状与防治方法。",
                tool_name="search_knowledge",
                tool_args={"query": disease, "top_k": 5},
            )

        # 4) 健康植株无需用药
        if disease and disease != HEALTHY_LABEL and not tried(history, "query_pesticide"):
            return Decision(
                thought=f"查询「{disease}」在「{crop}」上的登记农药。",
                tool_name="query_pesticide",
                tool_args={"disease_name": disease, "crop_type": crop},
            )

        # 5) 有绑定地块时补充农事上下文
        if ctx.field_id is not None and not tried(history, "get_field_context"):
            return Decision(thought="补充地块历史，确认是否为复发或连片发生。",
                            tool_name="get_field_context")

        # 6) 用药安全红线：重度 / 高价值作物低置信 / 证据缺失 → 必须转人工
        reason = self._human_review_reason(history, cnn, vlm, disease, crop)
        if reason and not tried(history, "request_human_review"):
            return Decision(thought=f"触发人工复核：{reason}", tool_name="request_human_review",
                            tool_args={"reason": reason})

        return Decision(thought="信息已足够，输出结构化诊断报告。", done=True)

    @staticmethod
    def _human_review_reason(history, cnn, vlm, disease, crop) -> Optional[str]:
        severity = (vlm or {}).get("severity") or cnn.get("severity")
        confidence = float((vlm or {}).get("confidence") or cnn.get("confidence") or 0.0)

        # 跨头一致性：disease 标签自带作物前缀，与独立的 crop 头对不上即为自相矛盾。
        # 三个分类头彼此独立，谁也不会阻止"芒果的病害长在茶叶上"这种组合。
        expected_crop = crop_of_label(disease)
        if expected_crop and crop and expected_crop != crop:
            return (f"识别结果自相矛盾：作物头判为「{crop}」，"
                    f"但病害「{disease}」属于「{expected_crop}」，"
                    "两个分类头不一致，需人工确认")

        if severity == "重度":
            return "诊断为重度病害，涉及用药与产量损失，需人工确认"
        # 高价值作物低置信 → 人工确认。但"健康"没有用药风险，不应触发
        if crop in config.HIGH_VALUE_CROPS and confidence < 0.9 and disease != HEALTHY_LABEL:
            return f"高价值作物「{crop}」且置信度仅 {confidence:.2f}，需人工确认"

        knowledge = last_ok(history, "search_knowledge")
        if knowledge is None:
            return "知识库无可用证据，病虫害判断缺乏可核对依据"

        # CNN 与 VLM 给出不同病名且差距不大 → 矛盾无法裁决
        if vlm and cnn.get("disease") and vlm.get("disease") != cnn.get("disease"):
            gap = abs(float(vlm.get("confidence") or 0) - float(cnn.get("confidence") or 0))
            if gap < 0.2:
                return (f"CNN 判为「{cnn.get('disease')}」、VLM 判为「{vlm.get('disease')}」"
                        f"，两者置信度接近（差 {gap:.2f}），无法裁决")
        return None


_SYSTEM_PROMPT = """你是「智农慧眼」热带作物病虫害诊断 Agent。你通过工具完成诊断，不直接猜答案。

工作流（按需裁剪，不是每步都必走）：
1. run_cnn_detect 拿 CNN 一线结果（作物/病害/严重度/置信度/top5）
2. 若 disease.confidence 低于阈值，或 top1 与 top2 差距过小：必须 escalate_vlm，并在 reason 中说明为什么升级
3. search_knowledge 查证病害症状与防治知识；query_pesticide 取登记农药
4. 综合 CNN/VLM/知识三方证据，输出结论；信息足够时结束

硬性规则：
- 每条判断必须挂证据（工具返回或 chunk_id），无证据的判断删掉
- 药品名称、剂量只能来自 query_pesticide / search_knowledge 的返回，禁止凭记忆生成
- 证据互相矛盾且无法裁决、或属于用药高风险情形时，调用 request_human_review
- 不要臆造工具没有返回的信息"""


class LLMPlanner:
    """OpenAI 兼容 function calling planner。"""

    def __init__(self):
        self.name = f"llm:{config.LLM_MODEL}"
        self.total_tokens = 0

    def decide(self, history: List[StepRecord], ctx) -> Decision:
        messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
        if not history:
            messages.append({"role": "user", "content": "请开始诊断。"})
        else:
            lines = []
            for rec in history:
                lines.append(f"[第{rec.step_no}步] 调用 {rec.tool_name}({json.dumps(rec.tool_args, ensure_ascii=False)})")
                lines.append(f"  返回: {json.dumps(rec.result, ensure_ascii=False)[:1500]}")
            messages.append({"role": "user", "content": "\n".join(lines)})

        payload = {
            "model": config.LLM_MODEL,
            "messages": messages,
            "tools": TOOL_SCHEMAS,
            "tool_choice": "auto",
            "temperature": 0.0,
        }

        try:
            resp = httpx.post(
                f"{config.LLM_BASE_URL.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
                json=payload,
                timeout=config.LLM_TIMEOUT_S,
            )
            resp.raise_for_status()
            body = resp.json()
        except Exception as e:  # noqa: BLE001 - planner 失败要让循环能降级
            return Decision(thought=f"LLM planner 调用失败（{type(e).__name__}: {e}），本次结束。", done=True)

        usage = body.get("usage") or {}
        self.total_tokens += int(usage.get("total_tokens") or 0)

        message = body["choices"][0]["message"]
        calls = message.get("tool_calls") or []
        if not calls:
            return Decision(thought=message.get("content") or "模型认为信息已足够。", done=True)

        call = calls[0]
        try:
            args = json.loads(call["function"].get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        return Decision(
            thought=message.get("content") or "",
            tool_name=call["function"]["name"],
            tool_args=args,
        )


def get_planner():
    """有 LLM_API_KEY 就用 LLM planner，否则退回确定性规则 planner。"""
    if config.llm_configured():
        return LLMPlanner()
    return RuleBasedPlanner()
