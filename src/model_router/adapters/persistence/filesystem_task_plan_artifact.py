from __future__ import annotations

import re
from pathlib import Path

from model_router.domain.task_analysis import TaskPlanNotFound


TASK_ID_PATTERN = re.compile(r"^task_[A-Za-z0-9_-]{1,96}$")


class FilesystemTaskPlanArtifact:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, task_id: str) -> Path:
        if not TASK_ID_PATTERN.fullmatch(str(task_id)):
            raise ValueError("invalid task id for plan artifact")
        path = (self.root / f"{task_id}.md").resolve()
        try:
            path.relative_to(self.root)
        except ValueError:
            raise ValueError("task plan path escapes artifact root") from None
        return path

    def save(self, task_id: str, markdown: str) -> None:
        if not isinstance(markdown, str) or not markdown.strip():
            raise ValueError("task plan markdown must not be empty")
        path = self._path(task_id)
        temporary = path.with_suffix(".md.tmp")
        try:
            temporary.write_text(markdown, encoding="utf-8", newline="\n")
            temporary.replace(path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def read(self, task_id: str) -> str:
        path = self._path(task_id)
        if not path.is_file():
            raise TaskPlanNotFound(f"task plan not found: {task_id}")
        return path.read_text(encoding="utf-8")
