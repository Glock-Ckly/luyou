from __future__ import annotations

from collections.abc import Mapping


MODEL_PROFILES = {
    "anthropic/claude-opus-4-8": {
        "strengths": ["deep reasoning", "architecture trade-offs", "long-context synthesis"],
        "limitations": ["high cost", "recommendation does not prove executor binding"],
        "suitable_task_types": ["architecture", "system_design", "deep_reasoning", "refactor"],
    },
    "anthropic/claude-sonnet-4-6": {
        "strengths": ["balanced reasoning", "implementation review", "requirements synthesis"],
        "limitations": ["not the cheapest bulk executor", "recommendation is executor-managed"],
        "suitable_task_types": ["architecture", "system_design", "implementation", "debugging"],
    },
    "anthropic/claude-haiku-4-5": {
        "strengths": ["low latency", "classification", "bounded transformations"],
        "limitations": ["limited deep architecture depth", "not preferred for high-risk changes"],
        "suitable_task_types": ["boilerplate", "bulk_generation", "data_processing"],
    },
    "openai/gpt-5.5-pro": {
        "strengths": ["deep reasoning", "complex systems analysis", "high-stakes review"],
        "limitations": ["very high cost", "reserve for T4 work"],
        "suitable_task_types": ["deep_reasoning", "architecture", "system_design"],
    },
    "openai/gpt-5.5": {
        "strengths": ["general reasoning", "architecture", "complex implementation planning"],
        "limitations": ["higher cost than workhorse models", "tool execution is not guaranteed"],
        "suitable_task_types": ["architecture", "system_design", "implementation", "debugging"],
    },
    "openai/gpt-5.4": {
        "strengths": ["balanced quality", "structured output", "cross-domain implementation"],
        "limitations": ["not specialized for repository editing", "recommendation is not execution"],
        "suitable_task_types": ["system_design", "implementation", "debugging", "refactor"],
    },
    "openai/gpt-5.4-mini": {
        "strengths": ["cost-efficient implementation", "classification", "bounded debugging"],
        "limitations": ["reduced depth on T3-T4 architecture", "requires stronger verification"],
        "suitable_task_types": ["implementation", "debugging", "boilerplate", "data_processing"],
    },
    "openai/gpt-5.4-nano": {
        "strengths": ["lowest latency tier", "simple extraction", "bulk transformations"],
        "limitations": ["not suitable for ambiguous architecture", "small-task scope only"],
        "suitable_task_types": ["boilerplate", "bulk_generation", "data_processing"],
    },
    "openai/gpt-5.3-codex": {
        "strengths": ["repository implementation", "test-driven coding", "multi-file debugging"],
        "limitations": ["execution environment controls actual model binding", "needs explicit tests"],
        "suitable_task_types": ["implementation", "debugging", "refactor", "code_patch", "file_edit"],
    },
    "deepseek/deepseek-v4-pro": {
        "strengths": ["cost-efficient deep reasoning", "technical planning", "code analysis"],
        "limitations": ["provider availability must be checked", "verification remains external"],
        "suitable_task_types": ["deep_reasoning", "architecture", "data_processing"],
    },
    "deepseek/deepseek-v4-flash": {
        "strengths": ["low cost", "fast classification", "bounded coding tasks"],
        "limitations": ["not preferred for high-risk T4 decisions", "requires fallback for complex work"],
        "suitable_task_types": ["implementation", "debugging", "refactor", "boilerplate"],
    },
}


def build_planning_model_catalog(runtime_catalog: Mapping[str, Mapping]) -> list[dict]:
    catalog: list[dict] = []
    for model_id, runtime_details in sorted(runtime_catalog.items()):
        if model_id == "cursor_queue":
            continue
        profile = MODEL_PROFILES.get(
            model_id,
            {
                "strengths": ["general model capability"],
                "limitations": ["no explicit capability profile; require conservative verification"],
                "suitable_task_types": ["uncertain"],
            },
        )
        catalog.append(
            {
                "id": model_id,
                "provider": model_id.split("/", 1)[0],
                "tier": str(runtime_details.get("tier") or "unknown"),
                "cost_per_mtok": dict(runtime_details.get("cost_per_mtok") or {}),
                "strengths": list(profile["strengths"]),
                "limitations": list(profile["limitations"]),
                "suitable_task_types": list(profile["suitable_task_types"]),
                "binding_mode": "EXECUTOR_MANAGED",
            }
        )
    return catalog
