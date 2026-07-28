from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol


class TaskPlanner(Protocol):
    async def analyze(
        self,
        goal: str,
        *,
        scope: str,
        model_catalog: Sequence[Mapping],
    ) -> Mapping: ...
