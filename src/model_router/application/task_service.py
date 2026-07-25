from __future__ import annotations

from model_router.domain.execution_task import ExecutionTask, TaskNotFound, TaskValidationError
from model_router.ports.task_repository import TaskRepository


class TaskService:
    def __init__(self, repository: TaskRepository):
        self.repository = repository

    def create(self, payload: dict) -> dict:
        fields = self._editable(payload)
        task = ExecutionTask.create(**fields)
        self.repository.add(task)
        return task.to_dict()

    def list(self, *, status: str | None = None, task_type: str | None = None, search: str | None = None) -> dict:
        tasks = self.repository.list(status=status, task_type=task_type, search=search)
        return {"items": [task.to_dict() for task in tasks], "total": len(tasks)}

    def get(self, task_id: str) -> dict:
        return self._require(task_id).to_dict()

    def update(self, task_id: str, payload: dict) -> dict:
        current = self._require(task_id)
        supplied_version = payload.get("version")
        if supplied_version is not None and int(supplied_version) != current.version:
            from model_router.domain.execution_task import TaskConflict

            raise TaskConflict("task version conflict")
        updated = current.update(**self._editable(payload))
        self.repository.update(updated, expected_version=current.version)
        return updated.to_dict()

    def delete(self, task_id: str) -> None:
        task = self._require(task_id)
        task.ensure_deletable()
        self.repository.delete(task_id)

    def _require(self, task_id: str) -> ExecutionTask:
        task = self.repository.get(task_id)
        if task is None:
            raise TaskNotFound(f"task not found: {task_id}")
        return task

    @staticmethod
    def _editable(payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise TaskValidationError("task payload must be an object")
        editable = {
            "title",
            "description",
            "task_type",
            "status",
            "priority",
            "technology_stack",
            "scope",
            "acceptance_criteria",
            "tags",
        }
        return {key: value for key, value in payload.items() if key in editable}
