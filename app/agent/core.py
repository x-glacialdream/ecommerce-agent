import json
import time
import uuid
from typing import Any, Dict, List, Tuple

from app.agent.planner import LLMPlanner
from app.agent.safety import SafetyManager
from app.services.memory import ContextCompressor
from app.services.registry import ToolRegistry
from app.schemas import StepTrace, TaskResponse
from app.utils.logger import get_logger, log_event


class EcommerceAgent:
    def __init__(self) -> None:
        self.registry = ToolRegistry()
        self.planner = LLMPlanner()
        self.safety = SafetyManager(max_steps=5, repeat_threshold=2)
        self.compressor = ContextCompressor(keep_last_n=3, max_summary_items=8)
        self.logger = get_logger("ecommerce_agent")

    def _new_request_id(self) -> str:
        return f"req_{uuid.uuid4().hex[:12]}"

    def _new_trace_id(self, step_idx: int) -> str:
        return f"trace_s{step_idx}_{uuid.uuid4().hex[:8]}"

    def run(self, user_input: str) -> TaskResponse:
        request_id = self._new_request_id()
        request_start = time.perf_counter()

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
                final_answer = action_input.get("final_answer", "任务已结束。")
                total_latency_ms = round((time.perf_counter() - request_start) * 1000, 2)

                log_event(
                    self.logger,
                    "info",
                    "agent_request_finished",
                    request_id=request_id,
                    trace_id=trace_id,
                    step=step_idx,
                    stop_reason=f"planner_finish:{decision_type}",
                    status="success",
                    total_latency_ms=total_latency_ms,
                    final_answer=final_answer,
                )

                return TaskResponse(
                    status="success",
                    final_answer=final_answer,
                    steps=steps,
                    stop_reason=f"planner_finish:{decision_type}"
                )

            if not self.registry.has_tool(action):
                total_latency_ms = round((time.perf_counter() - request_start) * 1000, 2)

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

                return TaskResponse(
                    status="failed",
                    final_answer=f"Tool not found: {action}",
                    steps=steps,
                    stop_reason="tool_not_found"
                )

            serialized_args = json.dumps(action_input, ensure_ascii=False, sort_keys=True)
            history.append((action, serialized_args))

            if self.safety.detect_loop(history):
                total_latency_ms = round((time.perf_counter() - request_start) * 1000, 2)

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

                return TaskResponse(
                    status="failed",
                    final_answer="Agent stopped due to loop detection.",
                    steps=steps,
                    stop_reason="loop_detected"
                )

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
                observation=observation
            )
            steps.append(trace)

            raw_steps.append({
                "step": step_idx,
                "trace_id": trace_id,
                "thought": thought,
                "decision_type": decision_type,
                "action": action,
                "action_input": action_input,
                "observation": observation
            })

            if self.safety.exceeded_max_steps(step_idx):
                total_latency_ms = round((time.perf_counter() - request_start) * 1000, 2)

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

                return TaskResponse(
                    status="failed",
                    final_answer="Agent stopped because max steps were reached.",
                    steps=steps,
                    stop_reason="max_steps_reached"
                )

        total_latency_ms = round((time.perf_counter() - request_start) * 1000, 2)

        log_event(
            self.logger,
            "error",
            "agent_request_unexpected_stop",
            request_id=request_id,
            stop_reason="unexpected_stop",
            status="failed",
            total_latency_ms=total_latency_ms,
        )

        return TaskResponse(
            status="failed",
            final_answer="Agent stopped unexpectedly.",
            steps=steps,
            stop_reason="unexpected_stop"
        )