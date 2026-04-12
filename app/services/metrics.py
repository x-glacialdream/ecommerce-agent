from __future__ import annotations

from threading import Lock
from typing import Any, Dict


class MetricsCollector:
    def __init__(self) -> None:
        self._lock = Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.total_requests = 0
            self.success_requests = 0
            self.failed_requests = 0
            self.total_latency_ms = 0.0
            self.action_counts: Dict[str, int] = {}

    def record_request(
        self,
        status: str,
        latency_ms: float,
        action_counts: Dict[str, int] | None = None,
    ) -> None:
        with self._lock:
            self.total_requests += 1
            self.total_latency_ms += latency_ms

            if status == "success":
                self.success_requests += 1
            else:
                self.failed_requests += 1

            if action_counts:
                for action, count in action_counts.items():
                    self.action_counts[action] = self.action_counts.get(action, 0) + count

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            average_latency_ms = (
                self.total_latency_ms / self.total_requests
                if self.total_requests > 0
                else 0.0
            )

            return {
                "total_requests": self.total_requests,
                "success_requests": self.success_requests,
                "failed_requests": self.failed_requests,
                "average_latency_ms": round(average_latency_ms, 2),
                "action_counts": dict(self.action_counts),
            }


metrics_collector = MetricsCollector()