from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from model_router.adapters.observability.in_memory import InMemoryExecutionObserver
from model_router.application.execution_service import ExecutionService
from model_router.application.provider_registry import ProviderRegistry
from model_router.domain.errors import ProviderTimeout
from model_router.domain.models import (
    ModelId,
    ModelResponse,
    ProviderHealth,
    RetryPolicy,
    TraceId,
)


class StubProvider:
    def __init__(self, *, available=True, actions=None):
        self.available = available
        self.actions = list(actions or [])
        self.calls = []

    async def health(self, provider_id):
        return ProviderHealth(provider_id, self.available, "stub")

    async def execute(self, request):
        self.calls.append(request.model_id.value)
        action = self.actions.pop(0)
        if isinstance(action, Exception):
            raise action
        return action


def response(model):
    return ModelResponse(ModelId.parse(model), "ok")


class ObservabilityAndRegistryTests(unittest.IsolatedAsyncioTestCase):
    async def test_unavailable_provider_is_skipped_before_execute(self):
        unavailable = StubProvider(available=False)
        healthy = StubProvider(actions=[response("anthropic/fallback")])
        registry = ProviderRegistry()
        registry.register("openai", unavailable)
        registry.register("anthropic", healthy)
        service = ExecutionService(registry=registry, retry_policy=RetryPolicy(max_retries=0))

        result = await service.execute(
            trace_id=TraceId("tr_health"),
            prompt="hello",
            candidates=[ModelId.parse("openai/primary"), ModelId.parse("anthropic/fallback")],
        )

        self.assertEqual([], unavailable.calls)
        self.assertEqual(["anthropic/fallback"], healthy.calls)
        self.assertEqual("skip_unavailable", result.attempts[0].action)
        self.assertEqual("success", result.outcome)

    async def test_metrics_count_retry_fallback_and_latency(self):
        provider = StubProvider(
            actions=[
                ProviderTimeout("one"),
                ProviderTimeout("two"),
                response("openai/fallback"),
            ]
        )
        observer = InMemoryExecutionObserver()
        service = ExecutionService(
            provider,
            RetryPolicy(max_retries=1),
            observer=observer,
            timeout_seconds=1,
        )

        await service.execute(
            trace_id=TraceId("tr_metrics"),
            prompt="hello",
            candidates=[ModelId.parse("openai/primary"), ModelId.parse("openai/fallback")],
        )

        metrics = observer.snapshot()["metrics"]
        self.assertEqual(1, metrics["requests"])
        self.assertEqual(1, metrics["successes"])
        self.assertEqual(2, metrics["failed_attempts"])
        self.assertEqual(1, metrics["retries"])
        self.assertEqual(1, metrics["fallbacks"])
        self.assertGreaterEqual(metrics["provider_latency_ms"], 1)
        self.assertTrue(observer.snapshot()["events"])


if __name__ == "__main__":
    unittest.main()
