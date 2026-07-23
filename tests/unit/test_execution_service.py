from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from model_router.application.execution_service import ExecutionService
from model_router.domain.errors import ProviderAuthenticationError, ProviderTimeout, ProviderUnavailable
from model_router.domain.models import ModelId, ModelResponse, RetryPolicy, TraceId


class FakeProvider:
    def __init__(self, actions: dict[str, list[object]]):
        self.actions = {model: list(values) for model, values in actions.items()}
        self.calls: list[str] = []

    async def execute(self, request):
        model = request.model_id.value
        self.calls.append(model)
        action = self.actions[model].pop(0)
        if isinstance(action, Exception):
            raise action
        return action


def response(model: str, content: str = "ok") -> ModelResponse:
    return ModelResponse(model_id=ModelId.parse(model), content=content)


class ExecutionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_primary_timeout_retries_then_falls_back(self):
        provider = FakeProvider({
            "openai/primary": [ProviderTimeout("timeout"), ProviderTimeout("timeout" )],
            "anthropic/fallback": [response("anthropic/fallback")],
        })
        service = ExecutionService(provider, RetryPolicy(max_retries=1), timeout_seconds=1)

        result = await service.execute(
            trace_id=TraceId.new(),
            prompt="hello",
            candidates=[ModelId.parse("openai/primary"), ModelId.parse("anthropic/fallback")],
        )

        self.assertEqual("success", result.outcome)
        self.assertEqual("anthropic/fallback", result.selected_model.value)
        self.assertEqual(
            ["retry", "fallback", "return_response"],
            [attempt.action for attempt in result.attempts],
        )
        self.assertEqual(["openai/primary", "openai/primary", "anthropic/fallback"], provider.calls)

    async def test_authentication_error_fails_fast(self):
        provider = FakeProvider({
            "openai/primary": [ProviderAuthenticationError("bad key")],
            "anthropic/fallback": [response("anthropic/fallback")],
        })
        service = ExecutionService(provider, RetryPolicy(max_retries=1), timeout_seconds=1)

        result = await service.execute(
            trace_id=TraceId.new(),
            prompt="hello",
            candidates=[ModelId.parse("openai/primary"), ModelId.parse("anthropic/fallback")],
        )

        self.assertEqual("failed", result.outcome)
        self.assertEqual("provider_authentication", result.final_error_type)
        self.assertEqual(["openai/primary"], provider.calls)

    async def test_all_candidates_failed_returns_normalized_result(self):
        provider = FakeProvider({
            "openai/primary": [ProviderUnavailable("down")],
            "anthropic/fallback": [ProviderUnavailable("down")],
        })
        service = ExecutionService(provider, RetryPolicy(max_retries=0), timeout_seconds=1)

        result = await service.execute(
            trace_id=TraceId.new(),
            prompt="hello",
            candidates=[ModelId.parse("openai/primary"), ModelId.parse("anthropic/fallback")],
        )

        self.assertEqual("all_providers_failed", result.outcome)
        self.assertIsNone(result.response)
        self.assertEqual("provider_unavailable", result.final_error_type)

    async def test_primary_success_has_one_attempt(self):
        provider = FakeProvider({"openai/primary": [response("openai/primary", "done")]})
        service = ExecutionService(provider, RetryPolicy(max_retries=1), timeout_seconds=1)

        result = await service.execute(
            trace_id=TraceId.new(),
            prompt="hello",
            candidates=[ModelId.parse("openai/primary")],
        )

        self.assertEqual("done", result.response.content)
        self.assertEqual(1, len(result.attempts))
        self.assertEqual("return_response", result.attempts[0].action)


if __name__ == "__main__":
    unittest.main()

