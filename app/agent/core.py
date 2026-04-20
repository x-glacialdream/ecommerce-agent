import json
import time
import uuid
from typing import Any, Dict, List, Tuple

from app.agent.planner import LLMPlanner
from app.agent.safety import SafetyManager
from app.services.memory import ContextCompressor
from app.services.metrics import metrics_collector
from app.services.registry import ToolRegistry
from app.schemas import StepTrace, TaskResponse
from app.utils.logger import get_logger, log_event


class BusinessOpsAgent:
    def __init__(self) -> None:
        self.registry = ToolRegistry()
        self.planner = LLMPlanner()
        self.safety = SafetyManager(max_steps=6, repeat_threshold=2)
        self.compressor = ContextCompressor(keep_last_n=4, max_summary_items=10)
        self.logger = get_logger("business_ops_agent")

    def _new_request_id(self) -> str:
        return f"req_{uuid.uuid4().hex[:12]}"

    def _new_trace_id(self, step_idx: int) -> str:
        return f"trace_s{step_idx}_{uuid.uuid4().hex[:8]}"

    def _count_actions(self, steps: List[StepTrace]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for step in steps:
            counts[step.action] = counts.get(step.action, 0) + 1
        return counts

    def _build_final_answer(
        self,
        user_input: str,
        steps: List[StepTrace],
        last_observation: Dict[str, Any] | None,
    ) -> str:
        if not steps:
            return "未执行任何有效步骤。"

        if last_observation and isinstance(last_observation, dict):
            if isinstance(last_observation.get("summary"), str) and last_observation.get("summary"):
                return last_observation["summary"]

            if isinstance(last_observation.get("message"), str) and last_observation.get("message"):
                return last_observation["message"]

            if isinstance(last_observation.get("result_text"), str) and last_observation.get("result_text"):
                return last_observation["result_text"]

        executed_actions = [step.action for step in steps]
        return (
            f"已完成任务处理。用户请求：{user_input}。"
            f"本次共执行 {len(steps)} 步，涉及工具：{', '.join(executed_actions)}。"
        )

    def _finalize_response(
        self,
        response: TaskResponse,
        start_time: float,
        steps: List[StepTrace],
    ) -> TaskResponse:
        latency_ms = (time.perf_counter() - start_time) * 1000
        metrics_collector.record_request(
            status=response.status,
            latency_ms=latency_ms,
            action_counts=self._count_actions(steps),
        )
        return response

    def run(self, user_input: str) -> TaskResponse:
        start_time = time.perf_counter()
        request_id = self._new_request_id()

        steps: List[StepTrace] = []
        raw_steps: List[Dict[str, Any]] = []
        history: List[Tuple[str, str]] = []
        last_observation: Dict[str, Any] | None = None

        log_event(
            self.logger,
            "info",
            "agent_request_started",
            request_id=request_id,
            user_input=user_input,
            max_steps=self.safety.max_steps,
            agent_type="business_ops",
        )

        for step_idx in range(1, self.safety.max_steps + 1):
            trace_id = self._new_trace_id(step_idx)

            context_payload = self.compressor.compress(raw_steps)

            log_event(
                self.logger,
                "info",
                "planner_decision_started",
                request_id=request_id,
                trace_id=trace_id,
                step=step_idx,
                compressed_history=context_payload.get("summary_text", ""),
                recent_step_count=len(context_payload.get("recent_steps", [])),
                has_compression=context_payload.get("has_compression", False),
            )

            decision = self.planner.decide(
                user_input=user_input,
                steps=raw_steps,
                context_payload=context_payload,
                last_observation=last_observation,
            )

            thought = decision["thought"]
            action = decision["action"]
            action_input = decision["action_input"]
            decision_type = decision.get("decision_type", "call_tool")

            log_event(
                self.logger,
                "info",
                "planner_decision_completed",
                request_id=request_id,
                trace_id=trace_id,
                step=step_idx,
                decision_type=decision_type,
                thought=thought,
                action=action,
                action_input=action_input,
            )

            if action == "finish":
                final_answer = action_input.get("final_answer")
                if not final_answer:
                    final_answer = self._build_final_answer(
                        user_input=user_input,
                        steps=steps,
                        last_observation=last_observation,
                    )

                total_latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

                final_status = "success"
                if last_observation is not None and not last_observation.get("success", True):
                    final_status = "failed"

                log_event(
                    self.logger,
                    "info" if final_status == "success" else "warning",
                    "agent_request_finished",
                    request_id=request_id,
                    trace_id=trace_id,
                    step=step_idx,
                    stop_reason=f"planner_finish:{decision_type}",
                    status=final_status,
                    total_latency_ms=total_latency_ms,
                    final_answer=final_answer,
                )

                response = TaskResponse(
                    status=final_status,
                    final_answer=final_answer,
                    steps=steps,
                    stop_reason=f"planner_finish:{decision_type}",
                )
                return self._finalize_response(response, start_time, steps)

            if not self.registry.has_tool(action):
                total_latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

                log_event(
                    self.logger,
                    "error",
                    "tool_not_found",
                    request_id=request_id,
                    trace_id=trace_id,
                    step=step_idx,
                    action=action,
                    action_input=action_input,
                    stop_reason="tool_not_found",
                    status="failed",
                    total_latency_ms=total_latency_ms,
                )

                response = TaskResponse(
                    status="failed",
                    final_answer=f"Tool not found: {action}",
                    steps=steps,
                    stop_reason="tool_not_found",
                )
                return self._finalize_response(response, start_time, steps)

            serialized_args = json.dumps(action_input, ensure_ascii=False, sort_keys=True)
            history.append((action, serialized_args))

            if self.safety.detect_loop(history):
                total_latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

                log_event(
                    self.logger,
                    "warning",
                    "loop_detected",
                    request_id=request_id,
                    trace_id=trace_id,
                    step=step_idx,
                    action=action,
                    action_input=action_input,
                    stop_reason="loop_detected",
                    status="failed",
                    total_latency_ms=total_latency_ms,
                )

                response = TaskResponse(
                    status="failed",
                    final_answer="Agent stopped due to loop detection.",
                    steps=steps,
                    stop_reason="loop_detected",
                )
                return self._finalize_response(response, start_time, steps)

            tool = self.registry.get_tool(action)
            tool_start = time.perf_counter()

            log_event(
                self.logger,
                "info",
                "tool_execution_started",
                request_id=request_id,
                trace_id=trace_id,
                step=step_idx,
                action=action,
                action_input=action_input,
            )

            try:
                observation = tool.run(**action_input)
            except Exception as e:
                observation = {
                    "success": False,
                    "error": f"Unhandled tool exception: {str(e)}",
                    "suggestion": "Check tool logic or input parameters",
                    "tool_name": action,
                }

            tool_latency_ms = round((time.perf_counter() - tool_start) * 1000, 2)
            last_observation = observation

            log_event(
                self.logger,
                "info" if observation.get("success") else "warning",
                "tool_execution_completed",
                request_id=request_id,
                trace_id=trace_id,
                step=step_idx,
                action=action,
                action_input=action_input,
                observation_success=observation.get("success"),
                error=observation.get("error"),
                suggestion=observation.get("suggestion"),
                tool_name=observation.get("tool_name"),
                latency_ms=tool_latency_ms,
            )

            trace = StepTrace(
                step=step_idx,
                thought=f"[{decision_type}] {thought}",
                action=action,
                action_input=action_input,
                observation=observation,
            )
            steps.append(trace)

            raw_steps.append(
                {
                    "step": step_idx,
                    "trace_id": trace_id,
                    "thought": thought,
                    "decision_type": decision_type,
                    "action": action,
                    "action_input": action_input,
                    "observation": observation,
                }
            )

            if self.safety.exceeded_max_steps(step_idx):
                total_latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

                log_event(
                    self.logger,
                    "warning",
                    "max_steps_reached",
                    request_id=request_id,
                    trace_id=trace_id,
                    step=step_idx,
                    stop_reason="max_steps_reached",
                    status="failed",
                    total_latency_ms=total_latency_ms,
                )

                response = TaskResponse(
                    status="failed",
                    final_answer="Agent stopped because max steps were reached.",
                    steps=steps,
                    stop_reason="max_steps_reached",
                )
                return self._finalize_response(response, start_time, steps)

        total_latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        log_event(
            self.logger,
            "error",
            "agent_request_unexpected_stop",
            request_id=request_id,
            stop_reason="unexpected_stop",
            status="failed",
            total_latency_ms=total_latency_ms,
        )

        response = TaskResponse(
            status="failed",
            final_answer="Agent stopped unexpectedly.",
            steps=steps,
            stop_reason="unexpected_stop",
        )
        return self._finalize_response(response, start_time, steps)