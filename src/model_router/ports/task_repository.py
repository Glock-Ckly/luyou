from __future__ import annotations

from typing import Protocol

from model_router.domain.execution_task import ExecutionTask


class TaskRepository(Protocol):
    def add(self, task: ExecutionTask) -> None: ...

    def get(self, task_id: str) -> ExecutionTask | None: ...

    def list(
        self, *, status: str | None = None, task_type: str | None = None, search: str | None = None
    ) -> list[ExecutionTask]: ...

    def update(self, task: ExecutionTask, *, expected_version: int) -> None: ...

    def delete(self, task_id: str) -> None: ...
