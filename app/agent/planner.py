import json
import os
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
        description="One of: query_sales_insight, detect_business_anomaly, audit_expense, query_internal_kb, finish"
    )
    action_input: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments for the selected action.",
    )
    reason: str = Field(description="Why this decision was made.")


class MockPlanner:
    """
    Rule-based fallback planner for business operations scenarios.
    """

    def extract_time_range(self, text: str) -> str:
        if "最近7天" in text or "近7天" in text or "过去7天" in text:
            return "last_7_days"
        if "最近30天" in text or "近30天" in text or "过去30天" in text:
            return "last_30_days"
        return "last_30_days"

    def extract_group_by(self, text: str) -> str:
        if "区域产品线" in text or "区域-产品线" in text or "组合" in text:
            return "region_product_line"
        if "区域" in text or "大区" in text:
            return "region"
        if "产品线" in text or "品类" in text:
            return "product_line"
        return "region"

    def extract_metric(self, text: str) -> str:
        if "销量" in text or "数量" in text or "件数" in text:
            return "quantity"
        return "sales_amount"

    def extract_kb_query(self, text: str) -> str:
        kb_map = [
            ("报销", "差旅报销制度"),
            ("发票", "发票提交要求"),
            ("对账", "财务对账异常处理SOP"),
            ("招采", "招采流程说明"),
            ("采购", "招采流程说明"),
            ("入职", "新员工入职流程"),
            ("培训", "培训制度"),
            ("区域销量异常", "区域销量异常处理规范"),
            ("销量异常", "区域销量异常处理规范"),
            ("异常处理", "区域销量异常处理规范"),
            ("产品线异常", "产品线异常波动排查指引"),
            ("波动排查", "产品线异常波动排查指引"),
            ("回访", "重点客户回访规则"),
            ("产品资料", "产品资料查询说明"),
            ("制度", "制度规范"),
            ("流程", "流程规范"),
            ("SOP", "流程规范"),
            ("政策", "业务政策"),
        ]
        for keyword, mapped in kb_map:
            if keyword in text:
                return mapped
        return text.strip() if text.strip() else "制度规范"

    def build_sales_args(self, text: str) -> Dict[str, Any]:
        return {
            "metric": self.extract_metric(text),
            "group_by": self.extract_group_by(text),
            "time_range": self.extract_time_range(text),
            "dimension_filter": {},
        }

    def build_anomaly_args(self, text: str) -> Dict[str, Any]:
        # 异常任务默认更敏感：
        # 1. 默认最近 7 天
        # 2. 默认按区域-产品线组合看，避免异常被摊平
        # 3. 默认阈值 20%
        explicit_time = self.extract_time_range(text)
        has_explicit_time = any(
            kw in text for kw in ["最近7天", "近7天", "过去7天", "最近30天", "近30天", "过去30天"]
        )
        has_explicit_group = any(
            kw in text for kw in ["区域", "大区", "产品线", "品类", "区域产品线", "区域-产品线", "组合"]
        )

        time_range = explicit_time if has_explicit_time else "last_7_days"
        group_by = self.extract_group_by(text) if has_explicit_group else "region_product_line"

        return {
            "metric": self.extract_metric(text),
            "group_by": group_by,
            "time_range": time_range,
            "threshold": 0.2,
        }

    def build_expense_args(self, text: str) -> Dict[str, Any]:
        return {
            "top_k": 10,
        }

    def build_kb_args(self, text: str) -> Dict[str, Any]:
        return {
            "query": self.extract_kb_query(text),
            "top_k": 3,
        }

    def _format_kb_finish(self, observation: Dict[str, Any]) -> str:
        data = observation.get("data", {}) if isinstance(observation, dict) else {}
        results = data.get("results", []) if isinstance(data, dict) else []
        if results:
            first = results[0]
            title = first.get("title", "知识库结果")
            content = first.get("content", "未检索到明确内容。")
            return f"根据知识库《{title}》：{content}"
        return "已完成知识库查询，但未检索到明确结果。"

    def _format_sales_finish(self, observation: Dict[str, Any]) -> str:
        if not isinstance(observation, dict):
            return "已完成销售分析。"

        summary = observation.get("summary")
        if isinstance(summary, str) and summary:
            return summary

        data = observation.get("data", {})
        if isinstance(data, dict):
            tool_summary = data.get("summary")
            if isinstance(tool_summary, str) and tool_summary:
                return tool_summary

        return "已完成销售分析。"

    def _format_anomaly_finish(self, observation: Dict[str, Any]) -> str:
        if not isinstance(observation, dict):
            return "已完成异常检测。"

        summary = observation.get("summary")
        if isinstance(summary, str) and summary:
            return summary

        data = observation.get("data", {})
        if isinstance(data, dict):
            tool_summary = data.get("summary")
            if isinstance(tool_summary, str) and tool_summary:
                return tool_summary

            anomalies = data.get("anomalies", [])
            if anomalies:
                first = anomalies[0]
                group = first.get("group", "未知对象")
                severity = first.get("severity", "unknown")
                deviation = first.get("deviation_ratio", "N/A")
                suggested_action = first.get("suggested_action")
                base_text = f"检测到异常，重点关注对象：{group}，严重程度：{severity}，偏离比例：{deviation}。"
                if suggested_action:
                    return f"{base_text} {suggested_action}"
                return base_text

        return "已完成异常检测，未发现需要特别提示的异常。"

    def _format_expense_finish(self, observation: Dict[str, Any]) -> str:
        if not isinstance(observation, dict):
            return "已完成报销审核。"

        summary = observation.get("summary")
        if isinstance(summary, str) and summary:
            return summary

        data = observation.get("data", {})
        if isinstance(data, dict):
            tool_summary = data.get("summary")
            if isinstance(tool_summary, str) and tool_summary:
                return tool_summary

            flagged_items = data.get("flagged_items", [])
            if flagged_items:
                return f"已完成报销审核，识别到 {len(flagged_items)} 条需复核记录。"

        return "已完成报销审核，未发现明显异常。"

    def _pick_anomaly_kb_query(self, text: str, steps: List[Dict[str, Any]]) -> str:
        if "区域" in text or "大区" in text:
            return "区域销量异常处理规范"
        if "产品线" in text or "品类" in text:
            return "产品线异常波动排查指引"

        for s in steps:
            if s.get("action") == "detect_business_anomaly":
                obs = s.get("observation", {}) or {}
                data = obs.get("data", {}) or {}
                group_by = data.get("group_by")
                if group_by == "region":
                    return "区域销量异常处理规范"
                if group_by == "product_line":
                    return "产品线异常波动排查指引"

        return "区域销量异常处理规范"

    def decide(
        self,
        user_input: str,
        steps: List[Dict[str, Any]],
        context_payload: Optional[Dict[str, Any]] = None,
        last_observation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        text = user_input.strip()

        # 复合任务 1：先做异常检测，再查制度
        if (
            ("异常" in text or "下滑" in text or "预警" in text or "波动" in text)
            and ("制度" in text or "规则" in text or "流程" in text or "建议" in text)
        ):
            if not steps:
                return {
                    "thought": "这是一个复合任务，先识别业务异常。",
                    "decision_type": "call_tool",
                    "action": "detect_business_anomaly",
                    "action_input": self.build_anomaly_args(text),
                    "reason": "先判断是否存在异常，再结合制度给出处理建议。",
                }

            last_action = steps[-1]["action"]
            last_obs = steps[-1]["observation"]

            if last_action == "detect_business_anomaly" and last_obs.get("success"):
                kb_query = self._pick_anomaly_kb_query(text, steps)
                return {
                    "thought": "异常检测结果已拿到，继续查询相关制度与处理规范。",
                    "decision_type": "switch_tool",
                    "action": "query_internal_kb",
                    "action_input": {"query": kb_query, "top_k": 3},
                    "reason": "复合任务第二阶段：补充制度依据和处理建议。",
                }

            if last_action == "query_internal_kb" and last_obs.get("success"):
                anomaly_answer = None
                for s in steps:
                    if s["action"] == "detect_business_anomaly" and s["observation"].get("success"):
                        anomaly_answer = self._format_anomaly_finish(s["observation"])
                        break

                kb_answer = self._format_kb_finish(last_obs)

                final_answer = (
                    f"{anomaly_answer or '已完成异常检测。'} "
                    f"{kb_answer}"
                )

                return {
                    "thought": "异常结果和制度依据都已齐备，可以结束。",
                    "decision_type": "finish",
                    "action": "finish",
                    "action_input": {"final_answer": final_answer},
                    "reason": "复合任务已完成。",
                }

        # 复合任务 2：先做报销审核，再查制度
        if (
            ("报销" in text or "发票" in text or "对账" in text or "审核" in text)
            and ("制度" in text or "规则" in text or "流程" in text or "说明" in text)
        ):
            if not steps:
                return {
                    "thought": "这是一个复合任务，先进行报销审核。",
                    "decision_type": "call_tool",
                    "action": "audit_expense",
                    "action_input": self.build_expense_args(text),
                    "reason": "先识别异常单据，再结合制度生成处理意见。",
                }

            last_action = steps[-1]["action"]
            last_obs = steps[-1]["observation"]

            if last_action == "audit_expense" and last_obs.get("success"):
                return {
                    "thought": "报销审核结果已拿到，继续查询报销制度。",
                    "decision_type": "switch_tool",
                    "action": "query_internal_kb",
                    "action_input": {"query": "差旅报销制度", "top_k": 3},
                    "reason": "复合任务第二阶段：补充制度依据。",
                }

            if last_action == "query_internal_kb" and last_obs.get("success"):
                expense_answer = None
                for s in steps:
                    if s["action"] == "audit_expense" and s["observation"].get("success"):
                        expense_answer = self._format_expense_finish(s["observation"])
                        break

                kb_answer = self._format_kb_finish(last_obs)

                final_answer = (
                    f"{expense_answer or '已完成报销审核。'} "
                    f"{kb_answer}"
                )

                return {
                    "thought": "报销审核结果和制度依据都已齐备，可以结束。",
                    "decision_type": "finish",
                    "action": "finish",
                    "action_input": {"final_answer": final_answer},
                    "reason": "复合任务已完成。",
                }

        # 工具失败后的闭环控制
        if last_observation and not last_observation.get("success", False):
            error_text = last_observation.get("error", "")

            if steps:
                last_action = steps[-1]["action"]

                if last_action == "audit_expense":
                    return {
                        "thought": "报销审核失败，改为查询相关制度并给出人工处理建议。",
                        "decision_type": "switch_tool",
                        "action": "query_internal_kb",
                        "action_input": {"query": "差旅报销制度", "top_k": 3},
                        "reason": "工具失败后切换到知识库解释路径。",
                    }

                if last_action == "detect_business_anomaly":
                    return {
                        "thought": "异常检测失败，终止并提示用户检查输入范围。",
                        "decision_type": "finish",
                        "action": "finish",
                        "action_input": {
                            "final_answer": f"异常检测执行失败：{error_text}。请检查查询时间范围、分组维度或数据文件。"
                        },
                        "reason": "当前无法自动修复。",
                    }

                if last_action == "query_sales_insight":
                    return {
                        "thought": "销售分析失败，终止并提示用户检查分析条件。",
                        "decision_type": "finish",
                        "action": "finish",
                        "action_input": {
                            "final_answer": f"销售分析执行失败：{error_text}。请检查时间范围、指标或分组条件。"
                        },
                        "reason": "当前无法自动修复。",
                    }

                if last_action == "query_internal_kb":
                    return {
                        "thought": "知识库查询失败，结束并向用户说明错误。",
                        "decision_type": "finish",
                        "action": "finish",
                        "action_input": {
                            "final_answer": f"知识库查询失败：{error_text}"
                        },
                        "reason": "未命中恢复策略。",
                    }

            return {
                "thought": "当前工具执行失败，结束并向用户说明错误。",
                "decision_type": "finish",
                "action": "finish",
                "action_input": {"final_answer": f"任务执行失败：{error_text}"},
                "reason": "未命中恢复策略。",
            }

        # 成功后的收尾逻辑
        if steps:
            last_action = steps[-1]["action"]
            last_obs = steps[-1]["observation"]

            if last_action == "query_internal_kb" and last_obs.get("success"):
                return {
                    "thought": "知识库结果已拿到，可以直接回复用户。",
                    "decision_type": "finish",
                    "action": "finish",
                    "action_input": {
                        "final_answer": self._format_kb_finish(last_obs)
                    },
                    "reason": "知识查询任务已完成。",
                }

            if last_action == "query_sales_insight" and last_obs.get("success"):
                return {
                    "thought": "销售分析结果已拿到，可以结束。",
                    "decision_type": "finish",
                    "action": "finish",
                    "action_input": {
                        "final_answer": self._format_sales_finish(last_obs)
                    },
                    "reason": "销售分析任务已完成。",
                }

            if last_action == "detect_business_anomaly" and last_obs.get("success"):
                return {
                    "thought": "异常检测结果已拿到，可以结束。",
                    "decision_type": "finish",
                    "action": "finish",
                    "action_input": {
                        "final_answer": self._format_anomaly_finish(last_obs)
                    },
                    "reason": "异常检测任务已完成。",
                }

            if last_action == "audit_expense" and last_obs.get("success"):
                return {
                    "thought": "报销审核结果已拿到，可以结束。",
                    "decision_type": "finish",
                    "action": "finish",
                    "action_input": {
                        "final_answer": self._format_expense_finish(last_obs)
                    },
                    "reason": "报销审核任务已完成。",
                }

        # 首轮路由：报销 / 发票 / 对账优先
        if "报销" in text or "发票" in text or "对账" in text or "审核" in text:
            return {
                "thought": "用户在咨询报销审核或对账问题，应调用报销审核工具。",
                "decision_type": "call_tool",
                "action": "audit_expense",
                "action_input": self.build_expense_args(text),
                "reason": "识别到财务审核类意图。",
            }

        # 首轮路由：异常检测
        if "异常" in text or "预警" in text or "下滑" in text or "波动" in text or "流失" in text:
            return {
                "thought": "用户在关注业务异常，应调用异常检测工具。",
                "decision_type": "call_tool",
                "action": "detect_business_anomaly",
                "action_input": self.build_anomaly_args(text),
                "reason": "识别到业务异常检测意图。",
            }

        # 首轮路由：知识查询
        if (
            "制度" in text
            or "规则" in text
            or "流程" in text
            or "SOP" in text
            or "政策" in text
            or "规范" in text
            or "怎么办" in text
        ):
            return {
                "thought": "用户在咨询制度或流程，应查询内部知识库。",
                "decision_type": "call_tool",
                "action": "query_internal_kb",
                "action_input": self.build_kb_args(text),
                "reason": "识别到制度/流程问答意图。",
            }

        # 首轮路由：销售分析
        if (
            "销量" in text
            or "销售" in text
            or "产品线" in text
            or "区域表现" in text
            or "大区表现" in text
            or "趋势" in text
            or "分析" in text
        ):
            return {
                "thought": "用户在咨询经营分析问题，应调用销售分析工具。",
                "decision_type": "call_tool",
                "action": "query_sales_insight",
                "action_input": self.build_sales_args(text),
                "reason": "识别到销售分析意图。",
            }

        return {
            "thought": "无法明确识别用户意图，结束并提示用户更具体描述。",
            "decision_type": "finish",
            "action": "finish",
            "action_input": {
                "final_answer": (
                    "暂时无法准确识别你的需求。请明确说明是要做销售分析、异常预警、报销审核，"
                    "还是查询内部制度/流程。"
                )
            },
            "reason": "意图不明确。",
        }


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

        self.client = None
        if self.enabled:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print("GEMINI_CLIENT_INIT_FAILED =", e)
                self.client = None
                self.enabled = False

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
你是一个企业内部数智化 AI Agent 的决策层，只能输出一个 JSON 对象，不要输出任何额外文字。

可用工具：
1. query_sales_insight(metric, group_by, time_range, dimension_filter): 查询销售分析结果
2. detect_business_anomaly(metric, group_by, time_range, threshold): 检测业务异常
3. audit_expense(top_k): 审核报销/对账异常
4. query_internal_kb(query, top_k): 查询内部制度、流程、政策和知识库
5. finish(final_answer): 结束任务并回复用户

决策要求：
- 根据用户任务、历史步骤和最近一次 observation，决定下一步。
- decision_type 只能是：call_tool, retry, switch_tool, finish
- action 只能是：query_sales_insight, detect_business_anomaly, audit_expense, query_internal_kb, finish
- 如果工具失败，需要判断是 retry / switch_tool / finish
- 如果用户任务是复合任务，可以执行多步
- 先做数据/异常识别，再做制度解释
- 异常任务默认可以更敏感，优先考虑较短窗口和更细粒度分析
- 优先保持简洁、可执行、参数完整
- 不要编造不存在的数据内容

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
        allowed_actions = {
            "query_sales_insight",
            "detect_business_anomaly",
            "audit_expense",
            "query_internal_kb",
            "finish",
        }

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
            "reason": str(data.get("reason", "默认原因")),
        }

    def decide(
        self,
        user_input: str,
        steps: List[Dict[str, Any]],
        context_payload: Optional[Dict[str, Any]] = None,
        last_observation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.enabled or not self.client:
            print("PLANNER_PATH = MockPlanner")
            return self.fallback.decide(user_input, steps, context_payload, last_observation)

        prompt = self._build_prompt(user_input, steps, context_payload, last_observation)

        try:
            print("PLANNER_PATH = Gemini")
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": PlannerDecision.model_json_schema(),
                },
            )
            parsed = json.loads(response.text)
            return self._normalize_decision(parsed)
        except Exception as e:
            print("PLANNER_PATH = Gemini -> Fallback due to exception:", e)
            return self.fallback.decide(user_input, steps, context_payload, last_observation)