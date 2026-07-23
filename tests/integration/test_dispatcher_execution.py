from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import relay_llm
from dispatcher import TaskDispatcher
from relay_llm import RelayLLMResponse
from routing_table import route
from task_decomposer import Subtask


class DispatcherExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_relay_dispatch_retries_and_falls_back(self):
        decision = route("boilerplate", "T1", 0.0)
        calls: list[str] = []

        async def call_llm(model, messages, **kwargs):
            calls.append(model)
            if len(calls) <= 2:
                raise TimeoutError("timeout")
            return RelayLLMResponse(content="fallback success", model=model)

        original = relay_llm.call_llm
        relay_llm.call_llm = call_llm
        try:
            result = await TaskDispatcher()._dispatch_relay_api(
                Subtask(prompt="generate code"),
                "boilerplate",
                {"summary": "", "direction": "", "codex_prompt": "generate code"},
                decision,
                "tr_dispatch_test",
            )
        finally:
            relay_llm.call_llm = original

        self.assertTrue(result.success)
        self.assertEqual(decision.fallback[0], result.model)
        self.assertEqual("tr_dispatch_test", result.trace_id)
        self.assertEqual(["retry", "fallback", "return_response"], [item["action"] for item in result.attempts])
        self.assertEqual([decision.primary, decision.primary, decision.fallback[0]], calls)

    async def test_brain_dispatch_executes_selected_provider(self):
        decision = route("architecture", "T4", 0.0)
        calls: list[str] = []

        async def call_llm(model, messages, **kwargs):
            calls.append(model)
            return RelayLLMResponse(content="architecture result", model=model)

        original = relay_llm.call_llm
        relay_llm.call_llm = call_llm
        try:
            result = await TaskDispatcher()._dispatch_brain_only(
                Subtask(prompt="design system"),
                "architecture",
                {"summary": "", "direction": "direction", "codex_prompt": "design system"},
                decision,
                "tr_brain_test",
            )
        finally:
            relay_llm.call_llm = original

        self.assertTrue(result.success)
        self.assertEqual(decision.primary, result.model)
        self.assertEqual([decision.primary], calls)
        self.assertEqual("architecture result", result.result)


if __name__ == "__main__":
    unittest.main()

