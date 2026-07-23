from __future__ import annotations

from collections import deque
from threading import Lock

from model_router.domain.models import ExecutionEvent


class InMemoryExecutionObserver:
    def __init__(self, max_events: int = 200):
        self._events = deque(maxlen=max_events)
        self._lock = Lock()
        self._metrics = {
            "requests": 0,
            "successes": 0,
            "failures": 0,
            "failed_attempts": 0,
            "retries": 0,
            "fallbacks": 0,
            "unavailable_skips": 0,
            "provider_latency_total_ms": 0,
            "provider_attempts": 0,
        }

    def record(self, event: ExecutionEvent) -> None:
        item = {
            "trace_id": event.trace_id.value,
            "kind": event.kind,
            "model": event.model_id.value if event.model_id else None,
            "status": event.status,
            "action": event.action,
            "latency_ms": event.latency_ms,
            "error_type": event.error_type,
        }
        with self._lock:
            self._events.append(item)
            if event.kind == "request_started":
                self._metrics["requests"] += 1
            elif event.kind == "request_finished":
                self._metrics["successes" if event.status == "success" else "failures"] += 1
            elif event.kind == "attempt":
                if event.status == "failed":
                    self._metrics["failed_attempts"] += 1
                if event.action == "retry":
                    self._metrics["retries"] += 1
                elif event.action == "fallback":
                    self._metrics["fallbacks"] += 1
                elif event.action == "skip_unavailable":
                    self._metrics["unavailable_skips"] += 1
                if event.attempted:
                    self._metrics["provider_latency_total_ms"] += event.latency_ms
                    self._metrics["provider_attempts"] += 1

    def snapshot(self) -> dict:
        with self._lock:
            metrics = dict(self._metrics)
            attempts = metrics.pop("provider_attempts")
            total_latency = metrics.pop("provider_latency_total_ms")
            metrics["provider_latency_ms"] = round(total_latency / attempts, 2) if attempts else 0
            return {"metrics": metrics, "events": list(self._events)}
