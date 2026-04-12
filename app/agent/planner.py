import json
import os
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

try:
    from google import genai
    HAS_GEMINI = True
except Exception:
    HAS_GEMINI = False


class PlannerDecision(BaseModel):
    thought: str = Field(description="Short reasoning for the next step.")
    decision_type: str = Field(
        description="One of: call_tool, retry, switch_tool, finish"
    )
    action: str = Field(
        description="One of: query_logistics, modify_order, query_kb, finish"
    )
    action_input: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments for the selected action."
    )
    reason: str = Field(description="Why this decision was made.")


class MockPlanner:
    """
    Rule-based fallback planner.
    """

    ORDER_ID_PATTERN = re.compile(r"(1001|1002|1003)")

    def extract_order_id(self, text: str) -> Optional[str]:
        match = self.ORDER_ID_PATTERN.search(text)
        return match.group(1) if match else None

    def extract_address(self, text: str) -> Optional[str]:
        markers = ["改成", "修改为", "地址改为", "new address is"]
        for marker in markers:
            if marker in text:
                return text.split(marker, 1)[1].strip(" ：:，,。.")
        return None

    def decide(
        self,
        user_input: str,
        steps: List[Dict[str, Any]],
        context_payload: Optional[Dict[str, Any]] = None,
        last_observation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        text = user_input.strip()
        order_id = self.extract_order_id(text)

        # 复合任务：先查物流，再查规则
        if "物流" in text and ("还能不能改地址" in text or "是否还能改地址" in text):
            if not steps:
                return {
                    "thought": "这是一个复合任务，先查物流状态。",
                    "decision_type": "call_tool",
                    "action": "query_logistics",
                    "action_input": {"order_id": order_id},
                    "reason": "先确认订单物流/发货状态，再判断是否需要查询规则。"
                }

            last_action = steps[-1]["action"]
            last_obs = steps[-1]["observation"]

            if last_action == "query_logistics" and last_obs.get("success"):
                return {
                    "thought": "物流信息已拿到，继续查询发货后修改地址规则。",
                    "decision_type": "switch_tool",
                    "action": "query_kb",
                    "action_input": {"query": "发货后修改地址", "top_k": 3},
                    "reason": "复合任务第二阶段：给出规则解释。"
                }

            if last_action == "query_kb" and last_obs.get("success"):
                logistics_data = None
                for s in steps:
                    if s["action"] == "query_logistics" and s["observation"].get("success"):
                        logistics_data = s["observation"]["data"]
                        break

                kb_data = last_obs["data"]
                kb_results = kb_data.get("results", [])
                kb_answer = kb_results[0]["content"] if kb_results else "未检索到明确规则。"

                if logistics_data:
                    final_answer = (
                        f"订单 {logistics_data['order_id']} 的物流状态是：{logistics_data['status']}，"
                        f"运单号：{logistics_data['tracking_no']}。另外，根据知识库规则：{kb_answer}"
                    )
                else:
                    final_answer = f"根据知识库规则：{kb_answer}"

                return {
                    "thought": "复合任务信息已经收集完成，可以结束。",
                    "decision_type": "finish",
                    "action": "finish",
                    "action_input": {"final_answer": final_answer},
                    "reason": "物流结果和规则解释都已齐备。"
                }

        # 工具失败后的闭环控制
        if last_observation and not last_observation.get("success", False):
            error_text = last_observation.get("error", "")

            if "cannot be modified" in error_text:
                return {
                    "thought": "订单无法直接修改，改为查询知识库规则。",
                    "decision_type": "switch_tool",
                    "action": "query_kb",
                    "action_input": {"query": "发货后修改地址", "top_k": 3},
                    "reason": "订单修改失败后切换到知识库解释。"
                }

            if "Missing required parameter" in error_text or "Missing required parameters" in error_text:
                return {
                    "thought": "缺少必要参数，终止并提示用户补充信息。",
                    "decision_type": "finish",
                    "action": "finish",
                    "action_input": {
                        "final_answer": f"任务执行失败：{error_text}。请补充完整订单号或地址信息。"
                    },
                    "reason": "当前无法自动修复缺失参数。"
                }

            if "not found in logistics system" in error_text:
                return {
                    "thought": "物流系统未查到结果，切换到知识库给出物流异常处理建议。",
                    "decision_type": "switch_tool",
                    "action": "query_kb",
                    "action_input": {"query": "物流异常", "top_k": 3},
                    "reason": "查询失败后转规则说明。"
                }

            return {
                "thought": "当前工具执行失败，结束并向用户说明错误。",
                "decision_type": "finish",
                "action": "finish",
                "action_input": {"final_answer": f"任务执行失败：{error_text}"},
                "reason": "未命中恢复策略。"
            }

        # 成功后的收尾逻辑
        if steps:
            last_action = steps[-1]["action"]
            last_obs = steps[-1]["observation"]

            if last_action == "query_kb" and last_obs.get("success"):
                kb_data = last_obs["data"]
                kb_results = kb_data.get("results", [])
                kb_answer = kb_results[0]["content"] if kb_results else "未检索到明确规则。"
                return {
                    "thought": "知识库结果已拿到，可以直接回复用户。",
                    "decision_type": "finish",
                    "action": "finish",
                    "action_input": {
                        "final_answer": f"根据知识库规则：{kb_answer}"
                    },
                    "reason": "知识查询任务已完成。"
                }

            if last_action == "query_logistics" and last_obs.get("success"):
                data = last_obs["data"]
                return {
                    "thought": "已经拿到物流信息，可以结束。",
                    "decision_type": "finish",
                    "action": "finish",
                    "action_input": {
                        "final_answer": f"订单 {data['order_id']} 的物流状态是：{data['status']}，运单号：{data['tracking_no']}"
                    },
                    "reason": "物流查询任务已完成。"
                }

            if last_action == "modify_order" and last_obs.get("success"):
                data = last_obs["data"]
                return {
                    "thought": "订单地址修改成功，可以结束。",
                    "decision_type": "finish",
                    "action": "finish",
                    "action_input": {
                        "final_answer": f"订单 {data['order_id']} 地址修改成功，新地址为：{data['new_address']}"
                    },
                    "reason": "订单修改任务已完成。"
                }

        # 首轮路由
        if "物流" in text or "快递" in text:
            return {
                "thought": "用户在查询物流信息，应调用物流工具。",
                "decision_type": "call_tool",
                "action": "query_logistics",
                "action_input": {"order_id": order_id},
                "reason": "识别到物流查询意图。"
            }

        if "修改地址" in text or "改地址" in text or "收货地址" in text:
            new_address = self.extract_address(text)
            return {
                "thought": "用户想修改订单地址，应调用订单修改工具。",
                "decision_type": "call_tool",
                "action": "modify_order",
                "action_input": {"order_id": order_id, "new_address": new_address},
                "reason": "识别到订单修改意图。"
            }

        if "退款" in text:
            return {
                "thought": "用户在咨询退款政策，应查询知识库。",
                "decision_type": "call_tool",
                "action": "query_kb",
                "action_input": {"query": "退款规则", "top_k": 3},
                "reason": "识别到退款规则咨询。"
            }

        if "发货后" in text and "改地址" in text:
            return {
                "thought": "用户在咨询发货后修改地址政策，应查询知识库。",
                "decision_type": "call_tool",
                "action": "query_kb",
                "action_input": {"query": "发货后修改地址", "top_k": 3},
                "reason": "识别到规则咨询。"
            }

        if "物流异常" in text or "物流没更新" in text:
            return {
                "thought": "用户在咨询物流异常处理，应查询知识库。",
                "decision_type": "call_tool",
                "action": "query_kb",
                "action_input": {"query": "物流异常", "top_k": 3},
                "reason": "识别到物流异常规则咨询。"
            }

        return {
            "thought": "无法明确识别用户意图，直接结束并提示用户更具体描述。",
            "decision_type": "finish",
            "action": "finish",
            "action_input": {
                "final_answer": "暂时无法准确识别你的需求，请提供订单号，并明确是查物流、改地址，还是咨询规则。"
            },
            "reason": "意图不明确。"
        }


class LLMPlanner:
    """
    Gemini-powered planner.
    Fallback to MockPlanner when API is unavailable or output is invalid.
    """

    def __init__(self) -> None:
        self.fallback = MockPlanner()
        self.enabled = HAS_GEMINI and bool(os.getenv("GEMINI_API_KEY"))
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        print("GEMINI_ENABLED =", self.enabled)
        print("GEMINI_MODEL =", self.model)
        print("GEMINI_API_KEY_EXISTS =", bool(os.getenv("GEMINI_API_KEY")))

        class LLMPlanner:
            """
            Gemini-powered planner.
            Fallback to MockPlanner when API is unavailable or output is invalid.
            """

            def __init__(self) -> None:
                self.fallback = MockPlanner()

                self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                self.enabled = HAS_GEMINI and bool(self.api_key)

                print("GEMINI_ENABLED =", self.enabled)
                print("GEMINI_MODEL =", self.model)
                print("GEMINI_API_KEY_EXISTS =", bool(self.api_key))

                if self.enabled:
                    self.client = genai.Client(api_key=self.api_key)
                else:
                    self.client = None

    def _build_context_text(
        self,
        steps: List[Dict[str, Any]],
        context_payload: Optional[Dict[str, Any]] = None,
    ) -> str:
        if not context_payload:
            return json.dumps(steps, ensure_ascii=False)

        summary_text = context_payload.get("summary_text", "")
        recent_steps = context_payload.get("recent_steps", [])
        has_compression = context_payload.get("has_compression", False)

        lines: List[str] = []

        if has_compression:
            lines.append("Earlier summarized steps:")
            lines.append(summary_text or "None")
            lines.append("")

        lines.append("Recent detailed steps:")
        if recent_steps:
            lines.append(json.dumps(recent_steps, ensure_ascii=False))
        else:
            lines.append("[]")

        return "\n".join(lines).strip()

    def _build_prompt(
        self,
        user_input: str,
        steps: List[Dict[str, Any]],
        context_payload: Optional[Dict[str, Any]],
        last_observation: Optional[Dict[str, Any]],
    ) -> str:
        context_text = self._build_context_text(steps, context_payload)

        return f"""
你是一个电商智能助理 Agent 的决策层，只能输出一个 JSON 对象，不要输出任何额外文字。

可用工具：
1. query_logistics(order_id): 查询订单物流
2. modify_order(order_id, new_address): 修改订单地址
3. query_kb(query, top_k): 查询电商规则知识库
4. finish(final_answer): 结束任务并回复用户

决策要求：
- 根据用户任务、历史步骤和最近一次 observation，决定下一步。
- decision_type 只能是：call_tool, retry, switch_tool, finish
- action 只能是：query_logistics, modify_order, query_kb, finish
- 如果工具失败，需要判断是 retry / switch_tool / finish
- 如果用户任务是复合任务，可以执行多步
- 优先保持简洁、可执行、参数完整
- 不要编造订单号或地址

用户输入：
{user_input}

历史步骤（压缩后上下文）：
{context_text}

最近 observation：
{json.dumps(last_observation, ensure_ascii=False)}

请输出 JSON，字段必须包含：
thought, decision_type, action, action_input, reason
""".strip()

    def _normalize_decision(self, data: Dict[str, Any]) -> Dict[str, Any]:
        allowed_decisions = {"call_tool", "retry", "switch_tool", "finish"}
        allowed_actions = {"query_logistics", "modify_order", "query_kb", "finish"}

        decision_type = data.get("decision_type", "finish")
        action = data.get("action", "finish")

        if decision_type not in allowed_decisions:
            decision_type = "finish"
        if action not in allowed_actions:
            action = "finish"

        action_input = data.get("action_input")
        if not isinstance(action_input, dict):
            action_input = {}

        return {
            "thought": str(data.get("thought", "根据当前上下文做出决策。")),
            "decision_type": decision_type,
            "action": action,
            "action_input": action_input,
            "reason": str(data.get("reason", "默认原因"))
        }

    def decide(
        self,
        user_input: str,
        steps: List[Dict[str, Any]],
        context_payload: Optional[Dict[str, Any]] = None,
        last_observation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.enabled or not self.client:
            return self.fallback.decide(user_input, steps, context_payload, last_observation)

        prompt = self._build_prompt(user_input, steps, context_payload, last_observation)

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_json_schema": PlannerDecision.model_json_schema(),
                },
            )
            parsed = json.loads(response.text)
            return self._normalize_decision(parsed)
        except Exception:
            return self.fallback.decide(user_input, steps, context_payload, last_observation)