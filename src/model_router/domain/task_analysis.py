from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace

from model_router.domain.execution_task import TASK_PRIORITIES, TASK_TYPES


COMPLEXITIES = {"T0", "T1", "T2", "T3", "T4"}
ANALYSIS_BINDING_MODES = {"EXECUTOR_MANAGED"}


class TaskAnalysisError(ValueError):
    pass


class TaskPlannerUnavailable(RuntimeError):
    pass


class TaskPlanningFailed(TaskAnalysisError):
    pass


class TaskPlanNotFound(LookupError):
    pass


def _mapping(value: object, field_name: str) -> Mapping:
    if not isinstance(value, Mapping):
        raise TaskAnalysisError(f"{field_name} must be an object")
    return value


def _required_text(value: object, field_name: str, *, maximum: int = 10000) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise TaskAnalysisError(f"{field_name} is required")
    if len(normalized) > maximum:
        raise TaskAnalysisError(f"{field_name} exceeds {maximum} characters")
    return normalized


def _optional_text(value: object, field_name: str, *, maximum: int = 10000) -> str:
    normalized = str(value or "").strip()
    if len(normalized) > maximum:
        raise TaskAnalysisError(f"{field_name} exceeds {maximum} characters")
    return normalized


def _choice(value: object, field_name: str, choices: set[str]) -> str:
    normalized = _required_text(value, field_name)
    if normalized not in choices:
        raise TaskAnalysisError(f"unsupported {field_name}: {normalized}")
    return normalized


def _integer(value: object, field_name: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TaskAnalysisError(f"{field_name} must be an integer")
    if not minimum <= value <= maximum:
        raise TaskAnalysisError(f"{field_name} must be between {minimum} and {maximum}")
    return value


def _boolean(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise TaskAnalysisError(f"{field_name} must be a boolean")
    return value


def _items(value: object, field_name: str, *, minimum: int, maximum: int) -> list:
    if isinstance(value, (str, bytes, Mapping)) or not isinstance(value, (list, tuple)):
        raise TaskAnalysisError(f"{field_name} must be an array")
    items = list(value)
    if not minimum <= len(items) <= maximum:
        raise TaskAnalysisError(f"{field_name} must contain {minimum} to {maximum} items")
    return items


def _strings(
    value: object,
    field_name: str,
    *,
    minimum: int,
    maximum: int,
    item_maximum: int = 500,
    lowercase: bool = False,
) -> tuple[str, ...]:
    normalized: list[str] = []
    for item in _items(value, field_name, minimum=minimum, maximum=maximum):
        text = _required_text(item, field_name, maximum=item_maximum)
        if lowercase:
            text = text.lower()
        if text not in normalized:
            normalized.append(text)
    if len(normalized) < minimum:
        raise TaskAnalysisError(f"{field_name} must contain {minimum} unique items")
    return tuple(normalized)


def _model(value: object, field_name: str, allowed_models: set[str]) -> str:
    model_id = _required_text(value, field_name, maximum=160)
    if model_id not in allowed_models:
        raise TaskAnalysisError(f"unsupported {field_name}: {model_id}")
    return model_id


@dataclass(frozen=True)
class AcceptanceCriterion:
    category: str
    criterion: str
    target_percent: int
    verification: str

    @classmethod
    def from_dict(cls, value: object) -> "AcceptanceCriterion":
        values = _mapping(value, "acceptance criterion")
        return cls(
            category=_required_text(values.get("category"), "criterion category", maximum=80).lower(),
            criterion=_required_text(values.get("criterion"), "criterion", maximum=1000),
            target_percent=_integer(
                values.get("target_percent"), "criterion target_percent", minimum=60, maximum=100
            ),
            verification=_required_text(values.get("verification"), "criterion verification", maximum=1000),
        )

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "criterion": self.criterion,
            "target_percent": self.target_percent,
            "verification": self.verification,
        }


@dataclass(frozen=True)
class SubtaskAnalysis:
    title: str
    description: str
    task_type: str
    complexity: str
    technology_stack: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    recommended_model: str
    fallback_models: tuple[str, ...]
    binding_mode: str

    @classmethod
    def from_dict(cls, value: object, *, allowed_models: set[str]) -> "SubtaskAnalysis":
        values = _mapping(value, "subtask")
        recommended_model = _model(values.get("recommended_model"), "recommended_model", allowed_models)
        fallback_models = _strings(
            values.get("fallback_models", []), "fallback_models", minimum=0, maximum=5, item_maximum=160
        )
        for model_id in fallback_models:
            _model(model_id, "fallback_model", allowed_models)
        return cls(
            title=_required_text(values.get("title"), "subtask title", maximum=120),
            description=_required_text(values.get("description"), "subtask description", maximum=4000),
            task_type=_choice(values.get("task_type"), "subtask task_type", TASK_TYPES),
            complexity=_choice(values.get("complexity"), "subtask complexity", COMPLEXITIES),
            technology_stack=_strings(
                values.get("technology_stack"), "subtask technology_stack", minimum=1, maximum=12
            ),
            acceptance_criteria=_strings(
                values.get("acceptance_criteria"),
                "subtask acceptance_criteria",
                minimum=1,
                maximum=20,
                item_maximum=1000,
            ),
            recommended_model=recommended_model,
            fallback_models=fallback_models,
            binding_mode=_choice(values.get("binding_mode"), "binding_mode", ANALYSIS_BINDING_MODES),
        )

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "task_type": self.task_type,
            "complexity": self.complexity,
            "technology_stack": list(self.technology_stack),
            "acceptance_criteria": list(self.acceptance_criteria),
            "recommended_model": self.recommended_model,
            "fallback_models": list(self.fallback_models),
            "binding_mode": self.binding_mode,
        }


@dataclass(frozen=True)
class ModelRecommendation:
    model_id: str
    role: str
    reason: str
    strengths: tuple[str, ...]
    limitations: tuple[str, ...]
    binding_mode: str

    @classmethod
    def from_dict(cls, value: object, *, allowed_models: set[str]) -> "ModelRecommendation":
        values = _mapping(value, "model recommendation")
        return cls(
            model_id=_model(values.get("model_id"), "model_id", allowed_models),
            role=_required_text(values.get("role"), "model role", maximum=120),
            reason=_required_text(values.get("reason"), "model reason", maximum=1000),
            strengths=_strings(values.get("strengths"), "model strengths", minimum=1, maximum=10),
            limitations=_strings(values.get("limitations"), "model limitations", minimum=1, maximum=10),
            binding_mode=_choice(values.get("binding_mode"), "binding_mode", ANALYSIS_BINDING_MODES),
        )

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "role": self.role,
            "reason": self.reason,
            "strengths": list(self.strengths),
            "limitations": list(self.limitations),
            "binding_mode": self.binding_mode,
        }


@dataclass(frozen=True)
class TaskAnalysis:
    goal: str
    goal_summary: str
    suggested_title: str
    description: str
    task_type: str
    complexity: str
    priority: str
    technology_stack: tuple[str, ...]
    scope: str
    coverage_target_percent: int
    acceptance_criteria: tuple[AcceptanceCriterion, ...]
    tags: tuple[str, ...]
    split_recommended: bool
    subtasks: tuple[SubtaskAnalysis, ...]
    needs_clarification: bool
    clarification_questions: tuple[str, ...]
    recommended_models: tuple[ModelRecommendation, ...]
    risks: tuple[str, ...]
    reasoning: str
    planner_model: str
    analysis_id: str
    content_hash: str

    @classmethod
    def from_dict(cls, value: object, *, allowed_models: Iterable[str]) -> "TaskAnalysis":
        values = _mapping(value, "analysis")
        allowed = {str(model_id).strip() for model_id in allowed_models if str(model_id).strip()}
        if not allowed:
            raise TaskAnalysisError("model catalog must not be empty")

        criteria = tuple(
            AcceptanceCriterion.from_dict(item)
            for item in _items(values.get("acceptance_criteria"), "acceptance_criteria", minimum=1, maximum=20)
        )
        split_recommended = _boolean(values.get("split_recommended"), "split_recommended")
        raw_subtasks = _items(values.get("subtasks", []), "subtasks", minimum=0, maximum=12)
        if split_recommended and not 2 <= len(raw_subtasks) <= 12:
            raise TaskAnalysisError("split analysis must contain 2 to 12 subtasks")
        if not split_recommended and raw_subtasks:
            raise TaskAnalysisError("subtasks require split_recommended=true")
        subtasks = tuple(SubtaskAnalysis.from_dict(item, allowed_models=allowed) for item in raw_subtasks)

        needs_clarification = _boolean(values.get("needs_clarification"), "needs_clarification")
        clarification_questions = _strings(
            values.get("clarification_questions", []),
            "clarification_questions",
            minimum=0,
            maximum=10,
            item_maximum=1000,
        )
        if needs_clarification and not clarification_questions:
            raise TaskAnalysisError("clarification questions are required when clarification is needed")

        recommendations = tuple(
            ModelRecommendation.from_dict(item, allowed_models=allowed)
            for item in _items(values.get("recommended_models"), "recommended_models", minimum=1, maximum=12)
        )
        goal_summary = _required_text(values.get("goal_summary"), "goal_summary", maximum=1000)
        provisional = cls(
            goal=_required_text(values.get("goal") or goal_summary, "goal", maximum=20000),
            goal_summary=goal_summary,
            suggested_title=_required_text(values.get("suggested_title"), "suggested_title", maximum=120),
            description=_required_text(values.get("description"), "description", maximum=10000),
            task_type=_choice(values.get("task_type"), "task_type", TASK_TYPES),
            complexity=_choice(values.get("complexity"), "complexity", COMPLEXITIES),
            priority=_choice(values.get("priority"), "priority", TASK_PRIORITIES),
            technology_stack=_strings(
                values.get("technology_stack"), "technology_stack", minimum=1, maximum=12
            ),
            scope=_optional_text(values.get("scope"), "scope"),
            coverage_target_percent=_integer(
                values.get("coverage_target_percent"),
                "coverage_target_percent",
                minimum=60,
                maximum=100,
            ),
            acceptance_criteria=criteria,
            tags=_strings(values.get("tags"), "tags", minimum=1, maximum=12, lowercase=True),
            split_recommended=split_recommended,
            subtasks=subtasks,
            needs_clarification=needs_clarification,
            clarification_questions=clarification_questions,
            recommended_models=recommendations,
            risks=_strings(values.get("risks", []), "risks", minimum=0, maximum=20, item_maximum=1000),
            reasoning=_required_text(values.get("reasoning"), "reasoning", maximum=4000),
            planner_model=_required_text(
                values.get("planner_model") or "deepseek/deepseek-chat", "planner_model", maximum=160
            ),
            analysis_id="",
            content_hash="",
        )
        canonical_json = json.dumps(
            provisional._canonical_data(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        content_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
        return replace(
            provisional,
            analysis_id=f"analysis_{content_hash[:20]}",
            content_hash=content_hash,
        )

    @property
    def initial_status(self) -> str:
        return "draft" if self.needs_clarification else "ready"

    def _canonical_data(self) -> dict:
        return {
            "goal": self.goal,
            "goal_summary": self.goal_summary,
            "suggested_title": self.suggested_title,
            "description": self.description,
            "task_type": self.task_type,
            "complexity": self.complexity,
            "priority": self.priority,
            "technology_stack": list(self.technology_stack),
            "scope": self.scope,
            "coverage_target_percent": self.coverage_target_percent,
            "acceptance_criteria": [criterion.to_dict() for criterion in self.acceptance_criteria],
            "tags": list(self.tags),
            "split_recommended": self.split_recommended,
            "subtasks": [subtask.to_dict() for subtask in self.subtasks],
            "needs_clarification": self.needs_clarification,
            "clarification_questions": list(self.clarification_questions),
            "recommended_models": [model.to_dict() for model in self.recommended_models],
            "risks": list(self.risks),
            "reasoning": self.reasoning,
            "planner_model": self.planner_model,
        }

    def to_task_payload(self) -> dict:
        criteria = [
            f"[{item.category}] {item.criterion} | target {item.target_percent}% | {item.verification}"
            for item in self.acceptance_criteria
        ]
        return {
            "title": self.suggested_title,
            "description": self.description,
            "task_type": self.task_type,
            "status": self.initial_status,
            "priority": self.priority,
            "technology_stack": list(self.technology_stack),
            "scope": self.scope,
            "acceptance_criteria": criteria,
            "tags": list(self.tags),
        }

    def to_dict(self) -> dict:
        values = self._canonical_data()
        values.update(
            {
                "analysis_id": self.analysis_id,
                "content_hash": self.content_hash,
                "initial_status": self.initial_status,
                "task": self.to_task_payload(),
                "checklist_markdown": self.to_markdown(),
            }
        )
        return values

    def to_markdown(self) -> str:
        lines = [
            f"# {self.suggested_title}",
            "",
            f"> Analysis: `{self.analysis_id}` | SHA-256: `{self.content_hash}` | Planner: `{self.planner_model}`",
            "",
            "## 目标",
            "",
            self.goal,
            "",
            "## 摘要",
            "",
            self.goal_summary,
            "",
            self.description,
            "",
            "## 分类",
            "",
            f"- 类型: `{self.task_type}`",
            f"- 复杂度: `{self.complexity}`",
            f"- 优先级: `{self.priority}`",
            f"- 初始状态: `{self.initial_status}`",
            f"- 目标通过率: `{self.coverage_target_percent}%`",
            f"- 标签: {', '.join(f'`{tag}`' for tag in self.tags)}",
            "",
            "## 技术栈",
            "",
            *[f"- {technology}" for technology in self.technology_stack],
            "",
            "## 范围边界",
            "",
            self.scope or "未指定，由执行阶段在安全边界内确认。",
            "",
            "## 验收标准",
            "",
        ]
        for criterion in self.acceptance_criteria:
            lines.extend(
                [
                    f"- [ ] [{criterion.category}] {criterion.criterion}",
                    f"  - 阈值: {criterion.target_percent}%",
                    f"  - 验证: {criterion.verification}",
                ]
            )
        lines.extend(["", "## 子任务", ""])
        if self.subtasks:
            for index, subtask in enumerate(self.subtasks, start=1):
                lines.extend(
                    [
                        f"### {index}. {subtask.title}",
                        "",
                        subtask.description,
                        "",
                        f"- 类型 / 复杂度: `{subtask.task_type}` / `{subtask.complexity}`",
                        f"- 技术栈: {', '.join(subtask.technology_stack)}",
                        f"- 推荐模型: `{subtask.recommended_model}`",
                        f"- 备选模型: {', '.join(f'`{model}`' for model in subtask.fallback_models) or '无'}",
                        f"- 绑定证据: `{subtask.binding_mode}`",
                        *[f"- [ ] {criterion}" for criterion in subtask.acceptance_criteria],
                        "",
                    ]
                )
        else:
            lines.extend(["无需拆分。", ""])
        lines.extend(["## 模型分配", ""])
        for recommendation in self.recommended_models:
            lines.extend(
                [
                    f"- `{recommendation.model_id}` / {recommendation.role} / `{recommendation.binding_mode}`",
                    f"  - 原因: {recommendation.reason}",
                    f"  - 优势: {', '.join(recommendation.strengths)}",
                    f"  - 边界: {', '.join(recommendation.limitations)}",
                ]
            )
        lines.extend(["", "## 风险", ""])
        lines.extend([f"- {risk}" for risk in self.risks] or ["- 未识别到额外风险；执行前仍需复核安全边界。"])
        if self.clarification_questions:
            lines.extend(["", "## 待澄清", "", *[f"- [ ] {question}" for question in self.clarification_questions]])
        lines.extend(
            [
                "",
                "## 确认清单",
                "",
                "- [ ] 用户已确认目标、范围和技术栈",
                "- [ ] 子任务边界互不重叠且未超出父任务范围",
                "- [ ] 模型推荐仅表示建议，未被声明为已执行或已验证",
                "- [ ] 验收方式可执行且通过率阈值明确",
                "- [ ] 安全、凭据、工作目录和审批边界未被放宽",
                "",
            ]
        )
        return "\n".join(lines)
