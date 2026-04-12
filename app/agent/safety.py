from typing import Dict, List, Tuple


class SafetyManager:
    def __init__(self, max_steps: int = 5, repeat_threshold: int = 2) -> None:
        self.max_steps = max_steps
        self.repeat_threshold = repeat_threshold

    def exceeded_max_steps(self, step_count: int) -> bool:
        return step_count >= self.max_steps

    def detect_loop(self, history: List[Tuple[str, str]]) -> bool:
        """
        Very simple loop detection:
        if the same (tool_name, serialized_args) appears repeatedly in recent history.
        """
        if len(history) < self.repeat_threshold + 1:
            return False

        last_item = history[-1]
        recent = history[-(self.repeat_threshold + 1):]
        same_count = sum(1 for item in recent if item == last_item)

        return same_count >= self.repeat_threshold + 1