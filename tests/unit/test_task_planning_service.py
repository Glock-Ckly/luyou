from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from model_router.application.task_planning_service import TaskPlanningService
from model_router.application.task_service import TaskService
from model_router.domain.task_analysis import TaskAnalysisError
from tests.unit.test_task_analysis import valid_analysis


class InMemoryTaskRepository:
    def __init__(self):
        self.items = {}

    def add(self, task):
        self.items[task.task_id] = task

    def get(self, task_id):
        return self.items.get(task_id)

    def list(self, **filters):
        del filters
        return list(self.items.values())

    def update(self, task, *, expected_version):
        del expected_version
        self.items[task.task_id] = task

    def delete(self, task_id, *, expected_status_not_in=()):
        del expected_status_not_in
        self.items.pop(task_id)


class FakePlanner:
    def __init__(self, response=None):
        self.response = response or valid_analysis()
        self.calls = []

    async def analyze(self, goal, *, scope, model_catalog):
        self.calls.append({"goal": goal, "scope": scope, "model_catalog": model_catalog})
        return self.response


class MemoryArtifact:
    def __init__(self, fail=False):
        self.fail = fail
        self.items = {}

    def save(self, task_id, markdown):
        if self.fail:
            raise OSError("simulated artifact failure")
        self.items[task_id] = markdown

    def read(self, task_id):
        return self.items[task_id]


CATALOG = [
    {"id": "anthropic/claude-sonnet-4-6"},
    {"id": "openai/gpt-5.4"},
    {"id": "openai/gpt-5.3-codex"},
]


class TaskPlanningServiceTests(unittest.IsolatedAsyncioTestCase):
    def service(self, *, planner=None, artifact=None, repository=None):
        repository = repository or InMemoryTaskRepository()
        return TaskPlanningService(
            task_service=TaskService(repository),
            planner=planner or FakePlanner(),
            artifact=artifact or MemoryArtifact(),
            model_catalog=CATALOG,
        ), repository

    async def test_analyze_uses_server_catalog_and_preserves_optional_scope(self):
        planner = FakePlanner()
        service, _ = self.service(planner=planner)
        result = await service.analyze({"goal": "Build and verify a secure service"})
        self.assertEqual("", planner.calls[0]["scope"])
        self.assertEqual(CATALOG, planner.calls[0]["model_catalog"])
        self.assertEqual("ready", result["task"]["status"])
        self.assertIn("## 验收标准", result["checklist_markdown"])

    async def test_analyze_rejects_short_goal_before_provider_call(self):
        planner = FakePlanner()
        service, _ = self.service(planner=planner)
        with self.assertRaises(TaskAnalysisError):
            await service.analyze({"goal": "short"})
        self.assertEqual([], planner.calls)

    async def test_create_from_analysis_persists_task_and_markdown(self):
        artifact = MemoryArtifact()
        service, repository = self.service(artifact=artifact)
        result = service.create_from_analysis({"analysis": valid_analysis()})
        task_id = result["task_id"]
        self.assertIn(task_id, repository.items)
        self.assertIn(task_id, artifact.items)
        self.assertEqual(f"/api/tasks/{task_id}/plan.md", result["plan_url"])

    async def test_artifact_failure_compensates_new_task(self):
        service, repository = self.service(artifact=MemoryArtifact(fail=True))
        with self.assertRaises(OSError):
            service.create_from_analysis({"analysis": valid_analysis()})
        self.assertEqual({}, repository.items)


if __name__ == "__main__":
    unittest.main()
