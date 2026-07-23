from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from model_router.adapters.providers.litellm_provider import LiteLLMProvider
from model_router.domain.errors import ProviderAuthenticationError, ProviderRateLimited, ProviderTimeout
from model_router.domain.models import ModelId, ModelRequest, ProviderId, TraceId


@dataclass
class RelayResponse:
    content: str
    model: str
    cost_usd: float = 0.25
    input_tokens: int = 12
    output_tokens: int = 8


class AuthenticationError(Exception):
    status_code = 401


class RateLimitError(Exception):
    status_code = 429


class LiteLLMProviderContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_normalizes_success_response(self):
        async def call(**kwargs):
            return RelayResponse(content="hello", model=kwargs["model"])

        adapter = LiteLLMProvider(call=call)
        request = ModelRequest(ModelId.parse("openai/gpt-5.4"), "prompt", TraceId.new())

        response = await adapter.execute(request)

        self.assertEqual("openai/gpt-5.4", response.model_id.value)
        self.assertEqual("hello", response.content)
        self.assertEqual(12, response.usage.input_tokens)
        self.assertEqual(8, response.usage.output_tokens)
        self.assertEqual(0.25, response.usage.cost_usd)

    async def test_maps_timeout(self):
        async def call(**kwargs):
            raise TimeoutError("socket timed out")

        with self.assertRaises(ProviderTimeout):
            await LiteLLMProvider(call=call).execute(
                ModelRequest(ModelId.parse("openai/gpt-5.4"), "prompt", TraceId.new())
            )

    async def test_maps_authentication_error(self):
        async def call(**kwargs):
            raise AuthenticationError("bad key")

        with self.assertRaises(ProviderAuthenticationError):
            await LiteLLMProvider(call=call).execute(
                ModelRequest(ModelId.parse("openai/gpt-5.4"), "prompt", TraceId.new())
            )

    async def test_maps_rate_limit_error(self):
        async def call(**kwargs):
            raise RateLimitError("slow down")

        with self.assertRaises(ProviderRateLimited):
            await LiteLLMProvider(call=call).execute(
                ModelRequest(ModelId.parse("openai/gpt-5.4"), "prompt", TraceId.new())
            )

    async def test_health_returns_provider_identity(self):
        health = await LiteLLMProvider(call=lambda **kwargs: None).health(ProviderId("openai"))
        self.assertEqual(ProviderId("openai"), health.provider_id)
        self.assertIsInstance(health.available, bool)


if __name__ == "__main__":
    unittest.main()

