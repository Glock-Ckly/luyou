from __future__ import annotations

from typing import Protocol


class TaskPlanArtifact(Protocol):
    def save(self, task_id: str, markdown: str) -> None: ...

    def read(self, task_id: str) -> str: ...
