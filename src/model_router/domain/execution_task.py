from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Iterable


TASK_TYPES = {
    "architecture",
    "system_design",
    "deep_reasoning",
    "implementation",
    "debugging",
    "refactor",
    "uncertain",
    "boilerplate",
    "bulk_generation",
    "data_processing",
    "code_patch",
    "file_edit",
}
TASK_STATUSES = {"draft", "ready", "running", "validating", "completed", "failed", "cancelled"}
TASK_PRIORITIES = {"low", "medium", "high", "urgent"}


class TaskValidationError(ValueError):
    pass


class TaskNotFound(LookupError):
    pass


class TaskConflict(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _required(value: object, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise TaskValidationError(f"{field_name} is required")
    return normalized


def _choice(value: object, field_name: str, supported: set[str]) -> str:
    normalized = _required(value, field_name)
    if normalized not in supported:
        raise TaskValidationError(f"unsupported {field_name}: {normalized}")
    return normalized


def _strings(values: Iterable[object] | None) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values or ():
        item = str(value).strip()
        if item and item not in normalized:
            normalized.append(item)
    return tuple(normalized)


@dataclass(frozen=True)
class ExecutionTask:
    task_id: str
    title: str
    description: str
    task_type: str
    status: str
    priority: str
    technology_stack: tuple[str, ...]
    scope: str
    acceptance_criteria: tuple[str, ...]
    tags: tuple[str, ...]
    version: int
    created_at: str
    updated_at: str

    @classmethod
    def create(
        cls,
        *,
        title: str,
        description: str,
        task_type: str,
        status: str = "draft",
        priority: str = "medium",
        technology_stack: Iterable[object] | None = None,
        scope: str = "",
        acceptance_criteria: Iterable[object] | None = None,
        tags: Iterable[object] | None = None,
        task_id: str | None = None,
        created_at: str | None = None,
    ) -> "ExecutionTask":
        timestamp = created_at or _now()
        return cls(
            task_id=task_id or f"task_{uuid.uuid4().hex}",
            title=_required(title, "title"),
            description=_required(description, "description"),
            task_type=_choice(task_type, "task_type", TASK_TYPES),
            status=_choice(status, "status", TASK_STATUSES),
            priority=_choice(priority, "priority", TASK_PRIORITIES),
            technology_stack=_strings(technology_stack),
            scope=str(scope or "").strip(),
            acceptance_criteria=_strings(acceptance_criteria),
            tags=_strings(tags),
            version=1,
            created_at=timestamp,
            updated_at=timestamp,
        )

    def update(self, **changes: object) -> "ExecutionTask":
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
        unknown = set(changes) - editable
        if unknown:
            raise TaskValidationError(f"unsupported task fields: {', '.join(sorted(unknown))}")
        values = self.to_dict()
        values.update(changes)
        return replace(
            self,
            title=_required(values["title"], "title"),
            description=_required(values["description"], "description"),
            task_type=_choice(values["task_type"], "task_type", TASK_TYPES),
            status=_choice(values["status"], "status", TASK_STATUSES),
            priority=_choice(values["priority"], "priority", TASK_PRIORITIES),
            technology_stack=_strings(values["technology_stack"]),
            scope=str(values["scope"] or "").strip(),
            acceptance_criteria=_strings(values["acceptance_criteria"]),
            tags=_strings(values["tags"]),
            version=self.version + 1,
            updated_at=_now(),
        )

    def ensure_deletable(self) -> None:
        if self.status in {"running", "validating"}:
            raise TaskConflict(f"task in {self.status} status cannot be deleted")

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "task_type": self.task_type,
            "status": self.status,
            "priority": self.priority,
            "technology_stack": list(self.technology_stack),
            "scope": self.scope,
            "acceptance_criteria": list(self.acceptance_criteria),
            "tags": list(self.tags),
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, values: dict) -> "ExecutionTask":
        return cls(
            task_id=str(values["task_id"]),
            title=str(values["title"]),
            description=str(values["description"]),
            task_type=str(values["task_type"]),
            status=str(values["status"]),
            priority=str(values["priority"]),
            technology_stack=_strings(values.get("technology_stack")),
            scope=str(values.get("scope") or ""),
            acceptance_criteria=_strings(values.get("acceptance_criteria")),
            tags=_strings(values.get("tags")),
            version=int(values["version"]),
            created_at=str(values["created_at"]),
            updated_at=str(values["updated_at"]),
        )
