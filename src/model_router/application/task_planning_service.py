from __future__ import annotations

from collections.abc import Mapping, Sequence

from model_router.application.task_service import TaskService
from model_router.domain.task_analysis import TaskAnalysis, TaskAnalysisError, TaskPlanningFailed
from model_router.ports.task_plan_artifact import TaskPlanArtifact
from model_router.ports.task_planner import TaskPlanner


class TaskPlanningService:
    def __init__(
        self,
        *,
        task_service: TaskService,
        planner: TaskPlanner,
        artifact: TaskPlanArtifact,
        model_catalog: Sequence[Mapping],
    ):
        self.task_service = task_service
        self.planner = planner
        self.artifact = artifact
        self.model_catalog = [dict(model) for model in model_catalog]
        self.allowed_models = {
            str(model.get("id") or "").strip() for model in self.model_catalog if model.get("id")
        }
        if not self.allowed_models:
            raise ValueError("model catalog must not be empty")

    async def analyze(self, payload: object) -> dict:
        values = self._payload(payload)
        goal = str(values.get("goal") or "").strip()
        if not 10 <= len(goal) <= 20000:
            raise TaskAnalysisError("goal must contain 10 to 20000 characters")
        scope_value = values.get("scope", "")
        if scope_value is not None and not isinstance(scope_value, str):
            raise TaskAnalysisError("scope must be a string")
        scope = str(scope_value or "").strip()
        if len(scope) > 10000:
            raise TaskAnalysisError("scope exceeds 10000 characters")

        raw_analysis = await self.planner.analyze(
            goal,
            scope=scope,
            model_catalog=self.model_catalog,
        )
        if not isinstance(raw_analysis, Mapping):
            raise TaskPlanningFailed("DeepSeek task analysis must be an object")
        normalized = dict(raw_analysis)
        normalized["goal"] = goal
        normalized["scope"] = scope
        try:
            analysis = TaskAnalysis.from_dict(normalized, allowed_models=self.allowed_models)
        except TaskAnalysisError as error:
            raise TaskPlanningFailed("DeepSeek task analysis violated the planning contract") from error
        return analysis.to_dict()

    def create_from_analysis(self, payload: object) -> dict:
        values = self._payload(payload)
        analysis_values = values.get("analysis")
        if not isinstance(analysis_values, Mapping):
            raise TaskAnalysisError("analysis must be an object")
        analysis = TaskAnalysis.from_dict(analysis_values, allowed_models=self.allowed_models)
        task = self.task_service.create(analysis.to_task_payload())
        try:
            self.artifact.save(task["task_id"], analysis.to_markdown())
        except Exception:
            self.task_service.delete(task["task_id"])
            raise
        return {
            "task_id": task["task_id"],
            "title": task["title"],
            "task": task,
            "analysis_id": analysis.analysis_id,
            "content_hash": analysis.content_hash,
            "plan_url": f"/api/tasks/{task['task_id']}/plan.md",
        }

    def read_plan(self, task_id: str) -> str:
        return self.artifact.read(task_id)

    @staticmethod
    def _payload(payload: object) -> Mapping:
        if not isinstance(payload, Mapping):
            raise TaskAnalysisError("task analysis payload must be an object")
        return payload
