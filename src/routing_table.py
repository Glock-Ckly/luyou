"""
Routing table v2.

Routes by task_type + T0-T4 complexity into primary/fallback chains, then applies
budget pressure by walking the chain without crossing each task type's floor.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


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


COMPLEXITY_ALIASES: dict[str, str] = {
    "trivial": "T0",
    "simple": "T1",
    "moderate": "T2",
    "complex": "T3",
    "deep_reasoning": "T4",
    "0": "T0",
    "1": "T1",
    "2": "T2",
    "3": "T3",
    "4": "T4",
    "5": "T4",
}

COMPLEXITY_ORDER = ["T0", "T1", "T2", "T3", "T4"]
COMPLEXITY_RANK = {tier: index for index, tier in enumerate(COMPLEXITY_ORDER)}

MODEL_TIER: dict[str, str] = {
    "cursor_queue": "queue",
    "anthropic/claude-opus-4-8": "brain",
    "anthropic/claude-sonnet-4-6": "workhorse",
    "anthropic/claude-haiku-4-5": "economy",
    "openai/gpt-5.5": "brain",
    "openai/gpt-5.5-pro": "brain",
    "openai/gpt-5.4": "workhorse",
    "openai/gpt-5.4-mini": "economy",
    "openai/gpt-5.4-nano": "flash",
    "openai/gpt-5.3-codex": "workhorse",
    "openai/gpt-5.4-pro": "brain",
    "openai/gpt-5.2": "workhorse",
    "deepseek/deepseek-v4-pro": "brain",
    "deepseek/deepseek-v4-flash": "flash",
}

TIER_RANK = {
    "flash": 0,
    "economy": 1,
    "workhorse": 2,
    "brain": 3,
    "queue": 2,
}

MODEL_COST: dict[str, tuple[float, float]] = {
    "cursor_queue": (0.0, 0.0),
    "openai/gpt-5.4-nano": (0.2, 1.25),
    "deepseek/deepseek-v4-flash": (0.14, 0.28),
    "openai/gpt-5.4-mini": (0.75, 4.5),
    "anthropic/claude-haiku-4-5": (1.0, 5.0),
    "openai/gpt-5.3-codex": (1.75, 14.0),
    "openai/gpt-5.2": (1.75, 14.0),
    "openai/gpt-5.4": (2.5, 15.0),
    "anthropic/claude-sonnet-4-6": (3.0, 15.0),
    "deepseek/deepseek-v4-pro": (0.435, 0.87),
    "openai/gpt-5.5": (5.0, 30.0),
    "anthropic/claude-opus-4-8": (5.0, 25.0),
    "openai/gpt-5.4-pro": (30.0, 180.0),
    "openai/gpt-5.5-pro": (30.0, 180.0),
}

MODEL_CATALOG: dict[str, dict[str, Any]] = {
    model: {
        "tier": MODEL_TIER[model],
        "cost_per_mtok": {"in": costs[0], "out": costs[1]},
    }
    for model, costs in MODEL_COST.items()
}


TASK_POLICY: dict[str, dict[str, str | CostLevel]] = {
    "architecture": {
        "executor": "brain_only",
        "floor": "anthropic/claude-sonnet-4-6",
        "cost_level": CostLevel.HIGH,
    },
    "system_design": {
        "executor": "brain_only",
        "floor": "openai/gpt-5.4",
        "cost_level": CostLevel.HIGH,
    },
    "deep_reasoning": {
        "executor": "brain_only",
        "floor": "anthropic/claude-opus-4-8",
        "cost_level": CostLevel.HIGH,
    },
    "implementation": {
        "executor": "codex",
        "floor": "deepseek/deepseek-v4-flash",
        "cost_level": CostLevel.MEDIUM,
    },
    "debugging": {
        "executor": "codex",
        "floor": "deepseek/deepseek-v4-flash",
        "cost_level": CostLevel.MEDIUM,
    },
    "refactor": {
        "executor": "codex",
        "floor": "deepseek/deepseek-v4-flash",
        "cost_level": CostLevel.MEDIUM,
    },
    "boilerplate": {
        "executor": "relay_api",
        "floor": "openai/gpt-5.4-nano",
        "cost_level": CostLevel.LOW,
    },
    "bulk_generation": {
        "executor": "relay_api",
        "floor": "openai/gpt-5.4-nano",
        "cost_level": CostLevel.LOW,
    },
    "data_processing": {
        "executor": "relay_api",
        "floor": "openai/gpt-5.4-nano",
        "cost_level": CostLevel.LOW,
    },
    "code_patch": {
        "executor": "cursor_queue",
        "floor": "openai/gpt-5.3-codex",
        "cost_level": CostLevel.LOW,
    },
    "file_edit": {
        "executor": "cursor_queue",
        "floor": "openai/gpt-5.3-codex",
        "cost_level": CostLevel.LOW,
    },
    "uncertain": {
        "executor": "codex",
        "floor": "deepseek/deepseek-v4-flash",
        "cost_level": CostLevel.MEDIUM,
    },
}


TASK_TO_MODEL: dict[tuple[str, str], dict[str, Any]] = {
    ("architecture", "T3"): {
        "primary": "openai/gpt-5.5",
        "fallback": ["anthropic/claude-opus-4-8", "anthropic/claude-sonnet-4-6"],
    },
    ("architecture", "T4"): {
        "primary": "anthropic/claude-opus-4-8",
        "fallback": ["openai/gpt-5.5", "openai/gpt-5.5-pro", "deepseek/deepseek-v4-pro"],
    },
    ("system_design", "T2"): {
        "primary": "anthropic/claude-sonnet-4-6",
        "fallback": ["openai/gpt-5.4", "openai/gpt-5.5"],
    },
    ("system_design", "T3"): {
        "primary": "openai/gpt-5.5",
        "fallback": ["anthropic/claude-opus-4-8", "anthropic/claude-sonnet-4-6"],
    },
    ("system_design", "T4"): {
        "primary": "anthropic/claude-opus-4-8",
        "fallback": ["openai/gpt-5.5", "deepseek/deepseek-v4-pro"],
    },
    ("deep_reasoning", "T3"): {
        "primary": "anthropic/claude-opus-4-8",
        "fallback": ["openai/gpt-5.5", "deepseek/deepseek-v4-pro"],
    },
    ("deep_reasoning", "T4"): {
        "primary": "openai/gpt-5.5-pro",
        "fallback": ["anthropic/claude-opus-4-8", "openai/gpt-5.5"],
    },
    ("implementation", "T1"): {
        "primary": "openai/gpt-5.4-mini",
        "fallback": ["deepseek/deepseek-v4-flash", "openai/gpt-5.3-codex"],
    },
    ("implementation", "T2"): {
        "primary": "openai/gpt-5.3-codex",
        "fallback": ["anthropic/claude-sonnet-4-6", "openai/gpt-5.4"],
    },
    ("implementation", "T3"): {
        "primary": "openai/gpt-5.5",
        "fallback": ["anthropic/claude-opus-4-8", "openai/gpt-5.3-codex"],
    },
    ("debugging", "T1"): {
        "primary": "openai/gpt-5.4-mini",
        "fallback": ["deepseek/deepseek-v4-flash", "openai/gpt-5.3-codex"],
    },
    ("debugging", "T2"): {
        "primary": "openai/gpt-5.3-codex",
        "fallback": ["anthropic/claude-sonnet-4-6", "openai/gpt-5.4"],
    },
    ("debugging", "T3"): {
        "primary": "openai/gpt-5.5",
        "fallback": ["anthropic/claude-opus-4-8", "openai/gpt-5.3-codex"],
    },
    ("refactor", "T1"): {
        "primary": "deepseek/deepseek-v4-flash",
        "fallback": ["openai/gpt-5.4-mini"],
    },
    ("refactor", "T2"): {
        "primary": "openai/gpt-5.3-codex",
        "fallback": ["anthropic/claude-sonnet-4-6", "openai/gpt-5.4"],
    },
    ("refactor", "T3"): {
        "primary": "anthropic/claude-opus-4-8",
        "fallback": ["openai/gpt-5.5", "openai/gpt-5.3-codex"],
    },
    ("boilerplate", "T0"): {
        "primary": "openai/gpt-5.4-nano",
        "fallback": ["deepseek/deepseek-v4-flash"],
    },
    ("boilerplate", "T1"): {
        "primary": "deepseek/deepseek-v4-flash",
        "fallback": ["openai/gpt-5.4-mini", "openai/gpt-5.4-nano"],
    },
    ("bulk_generation", "T0"): {
        "primary": "openai/gpt-5.4-nano",
        "fallback": ["deepseek/deepseek-v4-flash"],
    },
    ("bulk_generation", "T1"): {
        "primary": "deepseek/deepseek-v4-flash",
        "fallback": ["anthropic/claude-haiku-4-5", "openai/gpt-5.4-mini"],
    },
    ("data_processing", "T0"): {
        "primary": "openai/gpt-5.4-nano",
        "fallback": ["deepseek/deepseek-v4-flash"],
    },
    ("data_processing", "T1"): {
        "primary": "deepseek/deepseek-v4-flash",
        "fallback": ["openai/gpt-5.4-mini"],
    },
    ("data_processing", "T3"): {
        "primary": "deepseek/deepseek-v4-pro",
        "fallback": ["openai/gpt-5.5"],
    },
    ("code_patch", "T0"): {
        "primary": "cursor_queue",
        "fallback": ["openai/gpt-5.3-codex"],
    },
    ("code_patch", "T1"): {
        "primary": "cursor_queue",
        "fallback": ["openai/gpt-5.3-codex"],
    },
    ("file_edit", "T0"): {
        "primary": "cursor_queue",
        "fallback": ["openai/gpt-5.3-codex"],
    },
    ("file_edit", "T1"): {
        "primary": "cursor_queue",
        "fallback": ["openai/gpt-5.3-codex"],
    },
    ("file_edit", "T2"): {
        "primary": "cursor_queue",
        "fallback": ["openai/gpt-5.3-codex", "anthropic/claude-sonnet-4-6"],
    },
    ("uncertain", "T2"): {
        "primary": "anthropic/claude-sonnet-4-6",
        "fallback": ["openai/gpt-5.4", "deepseek/deepseek-v4-flash"],
    },
}

FALLBACK_CHAINS: dict[tuple[str, str], list[str]] = {
    key: [value["primary"], *value["fallback"]]
    for key, value in TASK_TO_MODEL.items()
}

TASK_COST: dict[str, CostLevel] = {
    task_type: policy["cost_level"]  # type: ignore[dict-item]
    for task_type, policy in TASK_POLICY.items()
}

BUDGET_ZONES = [
    (0.00, "green", "no intervention"),
    (0.60, "yellow", "non-critical tasks move one step along fallback chain"),
    (0.75, "orange", "non-critical tasks move to cheapest chain member above floor"),
    (0.90, "red", "non-critical tasks prefer flash while respecting floor"),
]

CRITICAL_TASKS = {"architecture", "system_design", "deep_reasoning"}


@dataclass(frozen=True)
class RouteEntry:
    task_type: str
    complexity: str
    executor: str
    floor: str
    primary: str
    fallback: list[str]

    @property
    def chain(self) -> list[str]:
        return [self.primary, *self.fallback]


@dataclass
class RoutingDecision:
    task_type: str
    complexity: str
    primary: str
    fallback: list[str]
    executor: str
    tier: str
    floor: str
    cost_level: CostLevel
    budget_zone: str = "green"
    base_primary: str | None = None
    complexity_adjusted: bool = False

    @property
    def model(self) -> str:
        return self.primary

    @property
    def complexity_tier(self) -> str:
        """Alias for API/dispatcher compatibility."""
        return self.complexity

    @property
    def fallback_chain(self) -> list[str]:
        return [self.primary, *self.fallback]


def normalize_task_type(task_type: str | TaskType) -> str:
    value = task_type.value if isinstance(task_type, TaskType) else str(task_type)
    return value if value in TASK_POLICY else TaskType.UNCERTAIN.value


def normalize_complexity(complexity: int | str) -> str:
    if isinstance(complexity, int):
        key = str(complexity)
    else:
        key = complexity.strip()
    normalized = COMPLEXITY_ALIASES.get(key.lower(), key.upper())
    if normalized not in COMPLEXITY_RANK:
        return "T2"
    return normalized


def _nearest_defined_complexity(task_type: str, complexity: str) -> str:
    available = [
        tier
        for current_task, tier in TASK_TO_MODEL
        if current_task == task_type
    ]
    if not available:
        return "T2"

    requested_rank = COMPLEXITY_RANK[complexity]
    ranked = sorted(available, key=lambda tier: COMPLEXITY_RANK[tier])
    higher_or_equal = [
        tier for tier in ranked if COMPLEXITY_RANK[tier] >= requested_rank
    ]
    if higher_or_equal:
        return higher_or_equal[0]
    return ranked[-1]


def _entry_for(task_type: str, complexity: str) -> RouteEntry:
    policy = TASK_POLICY[task_type]
    resolved_complexity = _nearest_defined_complexity(task_type, complexity)
    config = TASK_TO_MODEL.get((task_type, resolved_complexity))
    if config is None:
        config = TASK_TO_MODEL[("uncertain", "T2")]
        policy = TASK_POLICY["uncertain"]
        task_type = "uncertain"
        resolved_complexity = "T2"

    return RouteEntry(
        task_type=task_type,
        complexity=resolved_complexity,
        executor=str(policy["executor"]),
        floor=str(policy["floor"]),
        primary=str(config["primary"]),
        fallback=list(config["fallback"]),
    )


def _zone_for(budget_ratio: float) -> str:
    zone = "green"
    for threshold, name, _ in reversed(BUDGET_ZONES):
        if budget_ratio >= threshold:
            zone = name
            break
    return zone


def _tier_rank(model: str) -> int:
    return TIER_RANK.get(MODEL_TIER.get(model, "workhorse"), TIER_RANK["workhorse"])


def _cost_key(model: str) -> tuple[int, float, float]:
    input_cost, output_cost = MODEL_COST.get(model, (999.0, 999.0))
    return (_tier_rank(model), input_cost + output_cost, output_cost)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _floor_constrained_chain(entry: RouteEntry) -> list[str]:
    chain = _dedupe([*entry.chain, entry.floor])
    floor_rank = _tier_rank(entry.floor)
    return [
        model
        for model in chain
        if model == "cursor_queue" or _tier_rank(model) >= floor_rank
    ]


def _fallback_after(primary: str, chain: list[str]) -> list[str]:
    return [model for model in chain if model != primary]


def apply_complexity_adjustment(
    task_type: str | TaskType,
    complexity: int | str,
    model: str | None = None,
) -> RouteEntry | str:
    """Resolve task + complexity to the nearest configured routing entry."""
    del model
    normalized_task = normalize_task_type(task_type)
    normalized_complexity = normalize_complexity(complexity)
    return _entry_for(normalized_task, normalized_complexity)


def apply_budget_control(
    entry: RouteEntry | str,
    budget_ratio: float | str,
    legacy_budget_ratio: float | None = None,
) -> tuple[str, list[str], str] | tuple[str, str]:
    """Move through the fallback chain under budget pressure without crossing floor."""
    if not isinstance(entry, RouteEntry):
        task_type = normalize_task_type(entry)
        model = str(budget_ratio)
        synthetic = RouteEntry(
            task_type=task_type,
            complexity="T2",
            executor=str(TASK_POLICY[task_type]["executor"]),
            floor=str(TASK_POLICY[task_type]["floor"]),
            primary=model,
            fallback=[],
        )
        primary, _fallback, zone = apply_budget_control(
            synthetic,
            float(legacy_budget_ratio or 0.0),
        )
        return primary, zone

    budget_ratio = float(budget_ratio)
    zone = _zone_for(budget_ratio)
    if zone == "green":
        return entry.primary, entry.fallback, zone

    chain = _floor_constrained_chain(entry)
    primary_index = chain.index(entry.primary) if entry.primary in chain else 0

    if entry.task_type in CRITICAL_TASKS:
        if zone in {"orange", "red"}:
            selected = entry.floor
        else:
            selected = entry.primary
        return selected, _fallback_after(selected, chain), zone

    if zone == "yellow":
        primary_rank = _tier_rank(entry.primary)
        lower_tier = [model for model in chain if _tier_rank(model) < primary_rank]
        if lower_tier:
            selected = max(lower_tier, key=lambda model: (_tier_rank(model), -_cost_key(model)[1]))
        else:
            selected = chain[min(primary_index + 1, len(chain) - 1)]
    elif zone == "orange":
        selected = min(chain, key=_cost_key)
    else:
        flash_candidates = [
            model for model in chain if MODEL_TIER.get(model) == "flash"
        ]
        selected = min(flash_candidates or chain, key=_cost_key)

    return selected, _fallback_after(selected, chain), zone


def route(
    task_type: str | TaskType,
    complexity: int | str = "T2",
    budget_ratio: float = 0.0,
) -> RoutingDecision:
    """Return the v2 routing decision for a task type and T0-T4 complexity."""
    requested_complexity = normalize_complexity(complexity)
    entry = apply_complexity_adjustment(task_type, requested_complexity)
    primary, fallback, zone = apply_budget_control(entry, budget_ratio)

    return RoutingDecision(
        task_type=entry.task_type,
        complexity=entry.complexity,
        primary=primary,
        fallback=fallback,
        executor=entry.executor,
        tier=MODEL_TIER.get(primary, "workhorse"),
        floor=entry.floor,
        cost_level=TASK_COST.get(entry.task_type, CostLevel.MEDIUM),
        budget_zone=zone,
        base_primary=entry.primary,
        complexity_adjusted=entry.complexity != requested_complexity,
    )


if __name__ == "__main__":
    decisions = [
        route("architecture", complexity="T4", budget_ratio=0.2),
        route("implementation", complexity="T1", budget_ratio=0.3),
        route("boilerplate", complexity="T0", budget_ratio=0.5),
        route("implementation", complexity="T2", budget_ratio=0.8),
        route("deep_reasoning", complexity="T4", budget_ratio=0.85),
        route("data_processing", complexity="T3", budget_ratio=0.92),
        route("uncertain", complexity="T2", budget_ratio=0.1),
    ]

    for decision in decisions:
        adjusted = " [complexity->nearest]" if decision.complexity_adjusted else ""
        print(
            f"{decision.task_type:16s} {decision.complexity:2s} "
            f"executor={decision.executor:12s} "
            f"primary={decision.primary:34s} "
            f"tier={decision.tier:9s} zone={decision.budget_zone}"
            f"{adjusted}"
        )
