from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from model_router.adapters.persistence.sqlite_task_repository import SQLiteTaskRepository
from model_router.domain.execution_task import ExecutionTask, TaskConflict


class SQLiteTaskRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "tasks.db"
        self.repository = SQLiteTaskRepository(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_crud_persists_across_repository_instances(self):
        task = ExecutionTask.create(title="淘宝式工作台", description="实现嵌套 UI", task_type="implementation")
        self.repository.add(task)
        loaded = SQLiteTaskRepository(self.path).get(task.task_id)
        self.assertEqual(task.title, loaded.title)

        updated = task.update(status="ready", priority="urgent")
        self.repository.update(updated, expected_version=1)
        self.assertEqual("urgent", self.repository.get(task.task_id).priority)

        self.repository.delete(task.task_id)
        self.assertIsNone(self.repository.get(task.task_id))

    def test_filters_by_status_type_and_search(self):
        first = ExecutionTask.create(title="Frontend task", description="nested dashboard", task_type="implementation")
        second = ExecutionTask.create(title="Architecture", description="task boundaries", task_type="architecture", status="ready")
        self.repository.add(first)
        self.repository.add(second)
        self.assertEqual([second.task_id], [item.task_id for item in self.repository.list(status="ready")])
        self.assertEqual([first.task_id], [item.task_id for item in self.repository.list(task_type="implementation")])
        self.assertEqual([first.task_id], [item.task_id for item in self.repository.list(search="dashboard")])

    def test_version_conflict_is_rejected(self):
        task = ExecutionTask.create(title="A", description="B", task_type="implementation")
        self.repository.add(task)
        with self.assertRaises(TaskConflict):
            self.repository.update(task.update(title="new"), expected_version=99)


if __name__ == "__main__":
    unittest.main()
