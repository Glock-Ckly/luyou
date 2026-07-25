from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from model_router.domain.execution_task import ExecutionTask, TaskConflict, TaskValidationError


class ExecutionTaskTests(unittest.TestCase):
    def test_create_normalizes_collections(self):
        task = ExecutionTask.create(
            title="  Build catalog  ",
            description="  Add task CRUD  ",
            task_type="implementation",
            priority="high",
            acceptance_criteria=[" API works ", "", "Tests pass"],
            tags=["backend", " backend ", "tdd"],
        )
        self.assertEqual("Build catalog", task.title)
        self.assertEqual(("API works", "Tests pass"), task.acceptance_criteria)
        self.assertEqual(("backend", "tdd"), task.tags)
        self.assertEqual(1, task.version)

    def test_required_fields_are_validated(self):
        with self.assertRaises(TaskValidationError):
            ExecutionTask.create(title="", description="missing", task_type="implementation")

    def test_update_increments_version(self):
        task = ExecutionTask.create(title="A", description="B", task_type="architecture")
        updated = task.update(title="A2", status="ready")
        self.assertEqual("A2", updated.title)
        self.assertEqual("ready", updated.status)
        self.assertEqual(2, updated.version)

    def test_running_task_cannot_be_deleted(self):
        task = ExecutionTask.create(title="A", description="B", task_type="implementation")
        running = task.update(status="running")
        with self.assertRaises(TaskConflict):
            running.ensure_deletable()

    def test_invalid_status_is_rejected(self):
        with self.assertRaises(TaskValidationError):
            ExecutionTask.create(
                title="A", description="B", task_type="implementation", status="unknown"
            )


if __name__ == "__main__":
    unittest.main()
