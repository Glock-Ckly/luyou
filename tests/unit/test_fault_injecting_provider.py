from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from model_router.adapters.providers.fault_injecting_provider import FaultInjectingProvider
from model_router.domain.errors import ProviderAuthenticationError, ProviderTimeout
from model_router.domain.models import ModelId, ModelRequest, TraceId


class FaultInjectingProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_model_raises_configured_error(self):
        provider = FaultInjectingProvider(
            failed_models={"openai/gpt-5.4"},
            failure_mode="timeout",
        )

        with self.assertRaises(ProviderTimeout):
            await provider.execute(
                ModelRequest(ModelId.parse("openai/gpt-5.4"), "prompt", TraceId.new())
            )

    async def test_non_failed_model_returns_deterministic_response(self):
        provider = FaultInjectingProvider(failed_models=set(), failure_mode="timeout")
        response = await provider.execute(
            ModelRequest(ModelId.parse("openai/gpt-5.4"), "prompt", TraceId.new())
        )
        self.assertEqual("openai/gpt-5.4", response.model_id.value)
        self.assertIn("simulated", response.content)

    async def test_authentication_mode_is_fail_fast_error(self):
        provider = FaultInjectingProvider(
            failed_models={"openai/gpt-5.4"},
            failure_mode="authentication",
        )
        with self.assertRaises(ProviderAuthenticationError):
            await provider.execute(
                ModelRequest(ModelId.parse("openai/gpt-5.4"), "prompt", TraceId.new())
            )


if __name__ == "__main__":
    unittest.main()

