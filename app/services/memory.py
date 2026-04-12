from typing import Any, Dict, List


class ContextCompressor:
    """
    Compress long step history for planner consumption.

    Strategy:
    - keep the latest N steps in full detail
    - summarize earlier steps into short structured lines
    """

    def __init__(self, keep_last_n: int = 3, max_summary_items: int = 8) -> None:
        self.keep_last_n = keep_last_n
        self.max_summary_items = max_summary_items

    def _truncate_text(self, value: Any, max_len: int = 120) -> str:
        text = str(value)
        if len(text) <= max_len:
            return text
        return text[:max_len] + "..."

    def _summarize_step(self, step: Dict[str, Any], idx: int) -> str:
        thought = self._truncate_text(step.get("thought", ""), 60)
        action = step.get("action", "")
        action_input = self._truncate_text(step.get("action_input", {}), 80)
        observation = step.get("observation", {})
        decision_type = step.get("decision_type", "")

        if isinstance(observation, dict):
            success = observation.get("success")
            if success is True:
                data = self._truncate_text(observation.get("data", {}), 90)
                return (
                    f"[Step {idx}] decision_type={decision_type}, action={action}, "
                    f"input={action_input}, success=True, data={data}"
                )
            if success is False:
                error = self._truncate_text(observation.get("error", ""), 90)
                return (
                    f"[Step {idx}] decision_type={decision_type}, action={action}, "
                    f"input={action_input}, success=False, error={error}"
                )

        return (
            f"[Step {idx}] decision_type={decision_type}, thought={thought}, "
            f"action={action}, input={action_input}"
        )

    def compress(self, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not steps:
            return {
                "summary_text": "No previous steps.",
                "recent_steps": [],
                "compressed_steps": [],
                "has_compression": False,
            }

        if len(steps) <= self.keep_last_n:
            return {
                "summary_text": "History is short, no compression applied.",
                "recent_steps": steps,
                "compressed_steps": [],
                "has_compression": False,
            }

        split_index = len(steps) - self.keep_last_n
        old_steps = steps[:split_index]
        recent_steps = steps[split_index:]

        compressed_lines = []
        for i, step in enumerate(old_steps, start=1):
            compressed_lines.append(self._summarize_step(step, i))

        compressed_lines = compressed_lines[: self.max_summary_items]

        summary_text = "\n".join(compressed_lines).strip()
        if not summary_text:
            summary_text = "No summarized history."

        return {
            "summary_text": summary_text,
            "recent_steps": recent_steps,
            "compressed_steps": compressed_lines,
            "has_compression": True,
        }