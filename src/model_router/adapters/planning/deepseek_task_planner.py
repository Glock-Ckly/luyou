from __future__ import annotations

import json
import os
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path

from model_router.domain.execution_task import TASK_TYPES
from model_router.domain.task_analysis import TaskPlanningFailed, TaskPlannerUnavailable


PLANNER_MODEL = "deepseek/deepseek-chat"
PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "task_analysis.txt"


class DeepSeekTaskPlanner:
    def __init__(self, *, call: Callable[..., Awaitable] | None = None, prompt_path: Path | None = None):
        self._default_call = call is None
        if call is None:
            from relay_llm import call_llm

            call = call_llm
        self.call = call
        self.prompt_path = prompt_path or PROMPT_PATH

    async def analyze(
        self,
        goal: str,
        *,
        scope: str,
        model_catalog: Sequence[Mapping],
    ) -> Mapping:
        if self._default_call and not os.environ.get("DEEPSEEK_API_KEY", "").strip():
            raise TaskPlannerUnavailable("DeepSeek task planner is not configured")
        try:
            instructions = self.prompt_path.read_text(encoding="utf-8")
        except OSError as error:
            raise TaskPlannerUnavailable("Task analysis prompt is unavailable") from error

        request = {
            "goal": goal,
            "scope": scope,
            "task_types": sorted(TASK_TYPES),
            "model_catalog": list(model_catalog),
        }
        try:
            response = await self.call(
                model=PLANNER_MODEL,
                messages=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": json.dumps(request, ensure_ascii=False, sort_keys=True)},
                ],
                temperature=0.0,
                max_tokens=8192,
                response_format={"type": "json_object"},
            )
        except TaskPlannerUnavailable:
            raise
        except Exception as error:
            raise TaskPlanningFailed("DeepSeek task analysis request failed") from error

        try:
            parsed = json.loads(str(response.content).strip())
        except (AttributeError, TypeError, json.JSONDecodeError) as error:
            raise TaskPlanningFailed("DeepSeek returned invalid task analysis JSON") from error
        if not isinstance(parsed, dict):
            raise TaskPlanningFailed("DeepSeek task analysis must be a JSON object")
        parsed["planner_model"] = str(getattr(response, "model", PLANNER_MODEL) or PLANNER_MODEL)
        return parsed
