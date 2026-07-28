from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from model_router.adapters.persistence.filesystem_task_plan_artifact import FilesystemTaskPlanArtifact
from model_router.domain.task_analysis import TaskPlanNotFound


class FilesystemTaskPlanArtifactTests(unittest.TestCase):
    def test_markdown_round_trip_is_utf8(self):
        with tempfile.TemporaryDirectory() as directory:
            store = FilesystemTaskPlanArtifact(Path(directory))
            store.save("task_abc", "# 清单\n\n内容")
            self.assertEqual("# 清单\n\n内容", store.read("task_abc"))

    def test_invalid_task_id_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as directory:
            store = FilesystemTaskPlanArtifact(Path(directory))
            with self.assertRaises(ValueError):
                store.save("../escape", "bad")

    def test_missing_plan_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(TaskPlanNotFound):
                FilesystemTaskPlanArtifact(Path(directory)).read("task_missing")


if __name__ == "__main__":
    unittest.main()
