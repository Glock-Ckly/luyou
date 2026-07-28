from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from model_router.adapters.planning.deepseek_task_planner import DeepSeekTaskPlanner
from model_router.domain.task_analysis import TaskAnalysisError


class Response:
    def __init__(self, content: str):
        self.content = content
        self.model = "deepseek/deepseek-chat"


class DeepSeekTaskPlannerContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_deepseek_chat_and_passes_catalog_without_secrets(self):
        captured = {}

        async def call(**kwargs):
            captured.update(kwargs)
            return Response(json.dumps({"goal_summary": "x"}))

        planner = DeepSeekTaskPlanner(call=call)
        await planner.analyze("Build a service", scope="", model_catalog=[{"id": "openai/gpt-5.3-codex"}])
        self.assertEqual("deepseek/deepseek-chat", captured["model"])
        prompt = json.dumps(captured["messages"], ensure_ascii=False)
        self.assertIn("openai/gpt-5.3-codex", prompt)
        self.assertNotIn("API_KEY", prompt)
        self.assertEqual(0.0, captured["temperature"])
        self.assertEqual({"type": "json_object"}, captured["response_format"])

    async def test_invalid_json_raises_analysis_error(self):
        async def call(**kwargs):
            return Response("not-json")

        with self.assertRaises(TaskAnalysisError):
            await DeepSeekTaskPlanner(call=call).analyze("Build a service", scope="", model_catalog=[])


if __name__ == "__main__":
    unittest.main()
