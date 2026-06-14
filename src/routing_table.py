"""
Routing Table — 核心映射 + 任务感知降级链

改动核心: llm-router 的 complexity→profile→chain 维度翻转为 task_type→model 精确映射。

每条映射有自己的降级链 — 不让 DeepSeek 做架构设计。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TaskType(str, Enum):
    ARCHITECTURE = "architecture"
    SYSTEM_DESIGN = "system_design"
    DEEP_REASONING = "deep_reasoning"
    IMPLEMENTATION = "implementation"
    DEBUGGING = "debugging"
    REFACTOR = "refactor"
    BOILERPLATE = "boilerplate"
    BULK_GENERATION = "bulk_generation"
    DATA_PROCESSING = "data_processing"
    CODE_PATCH = "code_patch"
    FILE_EDIT = "file_edit"
    UNCERTAIN = "uncertain"


class CostLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ── 核心映射: task_type → model ──────────────────────────

TASK_TO_MODEL: dict[str, str] = {
    "architecture":      "anthropic/claude-sonnet-4-6",
    "system_design":     "anthropic/claude-sonnet-4-6",
    "deep_reasoning":    "anthropic/claude-opus-4-6",
    "implementation":    "openai/gpt-4o",
    "debugging":         "openai/gpt-4o",
    "refactor":          "openai/gpt-4o",
    "boilerplate":       "deepseek/deepseek-chat",
    "bulk_generation":   "deepseek/deepseek-chat",
    "data_processing":   "deepseek/deepseek-chat",
    "code_patch":        "cursor_queue",
    "file_edit":         "cursor_queue",
    "uncertain":         "openai/gpt-4o",
}

# ── 成本标记 ─────────────────────────────────────────────

TASK_COST: dict[str, CostLevel] = {
    "architecture":      CostLevel.MEDIUM,
    "system_design":     CostLevel.MEDIUM,
    "deep_reasoning":    CostLevel.HIGH,
    "implementation":    CostLevel.MEDIUM,
    "debugging":         CostLevel.MEDIUM,
    "refactor":          CostLevel.MEDIUM,
    "boilerplate":       CostLevel.LOW,
    "bulk_generation":   CostLevel.LOW,
    "data_processing":   CostLevel.LOW,
    "code_patch":        CostLevel.LOW,
    "file_edit":         CostLevel.LOW,
    "uncertain":         CostLevel.MEDIUM,
}

# ── 任务感知降级链 (不让 DeepSeek 做架构设计) ─────────────

FALLBACK_CHAINS: dict[str, list[str]] = {
    "architecture": [
        "anthropic/claude-sonnet-4-6",
        "openai/gpt-4o",
        # 不下探到 DeepSeek — 架构任务不能交给廉价模型
    ],
    "system_design": [
        "anthropic/claude-sonnet-4-6",
        "openai/gpt-4o",
    ],
    "deep_reasoning": [
        "anthropic/claude-opus-4-6",
        "anthropic/claude-sonnet-4-6",
        "openai/gpt-4o",
    ],
    "implementation": [
        "openai/gpt-4o",
        "anthropic/claude-sonnet-4-6",
        "deepseek/deepseek-chat",
    ],
    "debugging": [
        "openai/gpt-4o",
        "anthropic/claude-sonnet-4-6",
        "deepseek/deepseek-chat",
    ],
    "refactor": [
        "openai/gpt-4o",
        "anthropic/claude-sonnet-4-6",
        "deepseek/deepseek-chat",
    ],
    "boilerplate": [
        "deepseek/deepseek-chat",
        "openai/gpt-4o-mini",
        "openai/gpt-4o",
    ],
    "bulk_generation": [
        "deepseek/deepseek-chat",
        "openai/gpt-4o-mini",
    ],
    "data_processing": [
        "deepseek/deepseek-chat",
        "openai/gpt-4o-mini",
    ],
    "code_patch": [
        "cursor_queue",
        # Cursor 无 API，无法自动回退
    ],
    "file_edit": [
        "cursor_queue",
    ],
    "uncertain": [
        "openai/gpt-4o",
        "anthropic/claude-sonnet-4-6",
        "deepseek/deepseek-chat",
    ],
}

# ── 复杂度修正 ───────────────────────────────────────────

def apply_complexity_adjustment(
    task_type: str,
    complexity: int,  # 1-5
    model: str,
) -> str:
    """复杂度 1-2 降档省钱，4-5 升档保质量"""
    if complexity <= 2:
        downgrade_map = {
            "anthropic/claude-opus-4-6": "anthropic/claude-sonnet-4-6",
            "anthropic/claude-sonnet-4-6": "openai/gpt-4o",
            "openai/gpt-4o": "deepseek/deepseek-chat",
            "openai/gpt-4o-mini": "deepseek/deepseek-chat",
        }
        return downgrade_map.get(model, model)
    elif complexity >= 4:
        upgrade_map = {
            "deepseek/deepseek-chat": "openai/gpt-4o",
            "openai/gpt-4o": "anthropic/claude-sonnet-4-6",
            "openai/gpt-4o-mini": "openai/gpt-4o",
        }
        return upgrade_map.get(model, model)
    return model


# ── 渐进预算控制 (4 区) ──────────────────────────────────

BUDGET_ZONES = [
    (0.00, "green",  "no intervention"),
    (0.60, "yellow", "complexity <= 2 tasks downgrade one tier"),
    (0.75, "orange", "non-critical tasks downgrade to cheapest capable"),
    (0.90, "red",    "only architecture/deep_reasoning keep original model"),
]

CRITICAL_TASKS = {"architecture", "system_design", "deep_reasoning"}


def apply_budget_control(
    task_type: str,
    model: str,
    budget_ratio: float,  # 0.0-1.0
) -> tuple[str, str]:
    """根据预算消耗比例选择性降级。

    Returns:
        (model, zone_name)
    """
    zone = "green"
    for threshold, name, _ in reversed(BUDGET_ZONES):
        if budget_ratio >= threshold:
            zone = name
            break

    if zone == "green":
        return model, zone

    if zone == "yellow" and task_type not in CRITICAL_TASKS:
        # 非关键任务 + 复杂度 ≤ 2 → 降档
        cheap_map = {
            "anthropic/claude-opus-4-6": "anthropic/claude-sonnet-4-6",
            "anthropic/claude-sonnet-4-6": "openai/gpt-4o",
            "openai/gpt-4o": "deepseek/deepseek-chat",
        }
        return cheap_map.get(model, model), zone

    if zone == "orange":
        if task_type not in CRITICAL_TASKS:
            # 降级到最便宜可用模型
            cheap_map = {
                "anthropic/claude-opus-4-6": "deepseek/deepseek-chat",
                "anthropic/claude-sonnet-4-6": "deepseek/deepseek-chat",
                "openai/gpt-4o": "deepseek/deepseek-chat",
                "openai/gpt-4o-mini": "deepseek/deepseek-chat",
            }
            return cheap_map.get(model, model), zone

    if zone == "red":
        if task_type not in CRITICAL_TASKS:
            return "deepseek/deepseek-chat", zone

    return model, zone


# ── 路由决策 ─────────────────────────────────────────────

@dataclass
class RoutingDecision:
    task_type: str
    model: str
    cost_level: CostLevel
    fallback_chain: list[str]
    complexity_adjusted: bool = False
    budget_zone: str = "green"


def route(
    task_type: str,
    complexity: int = 3,
    budget_ratio: float = 0.0,
) -> RoutingDecision:
    """执行路由决策。

    Args:
        task_type: 分类后的任务类型
        complexity: 复杂度 1-5 (默认 3)
        budget_ratio: 预算消耗比例 (默认 0.0)

    Returns:
        RoutingDecision
    """
    # 1. 查主映射
    model = TASK_TO_MODEL.get(task_type, TASK_TO_MODEL["uncertain"])
    fallback = FALLBACK_CHAINS.get(task_type, FALLBACK_CHAINS["uncertain"])
    cost = TASK_COST.get(task_type, CostLevel.MEDIUM)

    # 2. 复杂度修正
    adjusted_model = apply_complexity_adjustment(task_type, complexity, model)
    complexity_adjusted = (adjusted_model != model)

    # 3. 预算控制
    final_model, zone = apply_budget_control(task_type, adjusted_model, budget_ratio)

    return RoutingDecision(
        task_type=task_type,
        model=final_model,
        cost_level=cost,
        fallback_chain=fallback,
        complexity_adjusted=complexity_adjusted,
        budget_zone=zone,
    )


# ── 自测 ─────────────────────────────────────────────────
if __name__ == "__main__":
    decisions = [
        route("architecture", complexity=5, budget_ratio=0.2),
        route("implementation", complexity=2, budget_ratio=0.3),
        route("boilerplate", complexity=1, budget_ratio=0.5),
        route("implementation", complexity=3, budget_ratio=0.8),
        route("deep_reasoning", complexity=5, budget_ratio=0.85),
        route("uncertain", complexity=3, budget_ratio=0.1),
    ]

    for d in decisions:
        adj = " [adj]" if d.complexity_adjusted else ""
        print(
            f"{d.task_type:20s} cplx={d.complexity_adjusted} "
            f"-> {d.model:40s} [{d.cost_level.value}] "
            f"zone={d.budget_zone} {adj}"
        )
