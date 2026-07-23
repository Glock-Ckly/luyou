from typing import Protocol

from model_router.domain.models import ExecutionEvent


class ExecutionObserver(Protocol):
    def record(self, event: ExecutionEvent) -> None:
        ...


class NullExecutionObserver:
    def record(self, event: ExecutionEvent) -> None:
        pass
