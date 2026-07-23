from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import dispatcher
from orchestrator import MultiModelOrchestrator, handle_prompt


class LegacyPathMustNotRun(MultiModelOrchestrator):
    async def _decompose(self, prompt):
        raise AssertionError("legacy orchestrator pipeline was used")


def fake_dispatch_result():
    subtask = SimpleNamespace(
        index=0,
        prompt="hello",
        task_type="implementation",
        model="openai/gpt-5.4",
        result="done",
        confidence=0.9,
        success=True,
        cursor_task_id=None,
    )
    return SimpleNamespace(
        trace_id="tr_compat",
        task_type="implementation",
        selected_executor="relay_api",
        reason="unified dispatcher",
        steps=["decompose", "classify", "route", "dispatch"],
        result="done",
        cost_level="medium",
        subtasks=[subtask],
    )


class OrchestratorCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.original = dispatcher.TaskDispatcher

        class FakeDispatcher:
            def __init__(self, *args, **kwargs):
                pass

            async def dispatch(self, prompt, *, workdir):
                return fake_dispatch_result()

        dispatcher.TaskDispatcher = FakeDispatcher

    async def asyncTearDown(self):
        dispatcher.TaskDispatcher = self.original

    async def test_orchestrator_class_delegates_to_dispatcher(self):
        result = await LegacyPathMustNotRun().handle("hello")
        self.assertEqual("implementation", result.task_type)
        self.assertEqual("openai/gpt-5.4", result.selected_model)
        self.assertEqual("done", result.result)

    async def test_handle_prompt_uses_same_dispatcher_response(self):
        result = await handle_prompt("hello")
        self.assertEqual("tr_compat", result["trace_id"])
        self.assertEqual("openai/gpt-5.4", result["selected_model"])


if __name__ == "__main__":
    unittest.main()
