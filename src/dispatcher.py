"""Task dispatcher for routing v2.

Flow:
prompt -> decompose -> classify -> route -> plan -> executor.
The public `dispatch_prompt()` JSON shape remains backward-compatible and only
adds v2 fields.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from budget_adapter import get_budget_ratio
from codex_executor import codex_available, run_codex
from cursor_queue import push as cursor_push
from l1_classifier import classify_l1
from l2_classifier import classify_l2, parse_l2_json
from model_router.adapters.providers.litellm_provider import LiteLLMProvider
from model_router.application.execution_service import ExecutionService
from model_router.domain.models import ModelId, RetryPolicy, TraceId
from relay_config import apply_relay_env
from routing_table import route
from task_decomposer import DecomposerResult, Subtask, decompose

apply_relay_env()

_PLANNER_PROMPT = (Path(__file__).parent / "prompts" / "planner.txt").read_text(
    encoding="utf-8"
).strip()

CURSOR_TYPES = {"code_patch", "file_edit"}
CODEX_TYPES = {"implementation", "debugging", "refactor", "uncertain"}
RELAY_API_TYPES = {"boilerplate", "bulk_generation", "data_processing"}
BRAIN_ONLY_TYPES = {"architecture", "system_design", "deep_reasoning"}
PLAN_PRO_MODEL = "deepseek/deepseek-v4-pro"
PLAN_FLASH_MODEL = "deepseek/deepseek-v4-flash"


@dataclass
class DispatchStep:
    phase: str
    detail: str
    status: str = "done"  # pending | running | done | error | skipped


@dataclass
class SubtaskDispatch:
    index: int
    prompt: str
    task_type: str
    executor: str
    model: str
    plan_summary: str
    direction: str
    result: str
    success: bool
    confidence: float = 0.0
    cursor_task_id: str | None = None
    primary: str = ""
    fallback: list[str] = field(default_factory=list)
    tier: str = ""
    complexity_tier: str = ""
    budget_zone: str = "green"
    trace_id: str = ""
    attempts: list[dict] = field(default_factory=list)


@dataclass
class DispatchResult:
    trace_id: str
    task_type: str
    selected_executor: str
    reason: str
    steps: list[str]
    timeline: list[DispatchStep]
    result: str
    cost_level: str
    workdir: str
    subtasks: list[SubtaskDispatch] = field(default_factory=list)
    codex_available: bool = False
    decomposed: bool = False


class TaskDispatcher:
    """Dispatches work; execution stays delegated to Codex, relay, or queue."""

    def __init__(self, l1_threshold: float = 0.7):
        self.l1_threshold = l1_threshold

    async def dispatch(
        self,
        prompt: str,
        *,
        workdir: str | Path,
    ) -> DispatchResult:
        work = str(Path(workdir).resolve())
        trace_id = TraceId.new().value
        timeline: list[DispatchStep] = []
        steps: list[str] = []
        sub_dispatches: list[SubtaskDispatch] = []

        steps.append("decompose")
        timeline.append(DispatchStep("decompose", "DeepSeek decomposes task", "running"))
        decomp = await self._decompose(prompt)
        timeline[-1] = DispatchStep(
            "decompose",
            f"{'split' if decomp.split else 'single'} task; {len(decomp.subtasks)} subtasks",
            "done",
        )

        budget_ratio = await get_budget_ratio()

        for sub in decomp.subtasks:
            steps.append("classify")
            timeline.append(DispatchStep("classify", f"subtask {sub.index}: L1/L2", "running"))
            classification = await self._classify(sub)
            task_type = classification["task_type"]
            timeline[-1] = DispatchStep(
                "classify",
                (
                    f"{task_type} "
                    f"(conf {classification.get('confidence', 0):.2f}, "
                    f"{classification.get('source', '?')})"
                ),
                "done",
            )

            steps.append("route")
            decision = route(
                task_type=task_type,
                complexity=classification.get("complexity", 2),
                budget_ratio=budget_ratio,
            )
            timeline.append(
                DispatchStep(
                    "route",
                    (
                        f"{decision.model} via {decision.executor} "
                        f"({decision.complexity_tier}, {decision.tier}, {decision.budget_zone})"
                    ),
                    "done",
                )
            )

            steps.append("plan")
            planner_model = self._planner_model(decision.complexity_tier)
            timeline.append(DispatchStep("plan", f"{planner_model} generates direction", "running"))
            plan = await self._plan(sub.prompt, task_type, classification, planner_model, decision.executor)
            executor = self._resolve_executor(task_type, plan.get("executor", ""), decision.executor)
            timeline[-1] = DispatchStep(
                "plan",
                f"{plan.get('summary', '')[:60]} -> {executor}",
                "done",
            )

            steps.append("dispatch")
            timeline.append(DispatchStep("dispatch", f"dispatch to {executor}", "running"))

            if executor == "cursor_queue":
                sub_dispatches.append(self._dispatch_cursor(sub, task_type, plan, decision, trace_id))
                timeline[-1] = DispatchStep(
                    "dispatch",
                    f"Cursor Queue {sub_dispatches[-1].cursor_task_id}",
                    "done",
                )
            elif executor == "brain_only":
                brain_result = await self._dispatch_brain_only(sub, task_type, plan, decision, trace_id)
                sub_dispatches.append(brain_result)
                timeline[-1] = DispatchStep(
                    "dispatch",
                    f"brain provider {brain_result.model}",
                    "done" if brain_result.success else "error",
                )
            elif executor == "relay_api":
                relay_result = await self._dispatch_relay_api(sub, task_type, plan, decision, trace_id)
                sub_dispatches.append(relay_result)
                timeline[-1] = DispatchStep(
                    "dispatch",
                    f"relay_api {decision.model}",
                    "done" if relay_result.success else "error",
                )
            else:
                codex_result = await self._dispatch_codex(sub, task_type, plan, decision, work, trace_id)
                sub_dispatches.append(codex_result)
                timeline[-1] = DispatchStep(
                    "dispatch",
                    f"Codex with {decision.model}",
                    "done" if codex_result.success else "error",
                )

        steps.append("aggregate")
        return self._aggregate(sub_dispatches, steps, timeline, work, decomp.split, trace_id)

    async def _decompose(self, prompt: str) -> DecomposerResult:
        from relay_llm import call_llm

        async def _call(model, messages, **kwargs):
            return await call_llm(model=model, messages=messages, **kwargs)

        return await decompose(prompt, call_llm=_call)

    async def _classify(self, subtask: Subtask) -> dict:
        if subtask.type_hint:
            return {
                "task_type": subtask.type_hint,
                "complexity": 2,
                "confidence": 0.8,
                "reasoning": f"decomposer type_hint: {subtask.type_hint}",
                "source": "decomposer",
            }

        l1 = classify_l1(subtask.prompt, confidence_threshold=self.l1_threshold)
        if l1 is not None:
            complexity = 0 if l1.task_type in CURSOR_TYPES and len(subtask.prompt) < 120 else 2
            return {
                "task_type": l1.task_type,
                "complexity": complexity,
                "confidence": l1.confidence,
                "reasoning": l1.reasoning,
                "source": "L1",
            }

        return await classify_l2(subtask.prompt)

    async def _plan(
        self,
        prompt: str,
        task_type: str,
        classification: dict,
        planner_model: str,
        default_executor: str,
    ) -> dict:
        from relay_llm import call_llm

        user = (
            f"Task type: {task_type}\n"
            f"Default executor: {default_executor}\n"
            f"Classification: {json.dumps(classification, ensure_ascii=False)}\n"
            f"User task:\n{prompt}"
        )
        try:
            resp = await call_llm(
                model=planner_model,
                messages=[
                    {"role": "system", "content": _PLANNER_PROMPT},
                    {"role": "user", "content": user},
                ],
                temperature=0.0,
                max_tokens=1024,
            )
            return self._parse_plan(resp.content, task_type, default_executor)
        except Exception as e:
            return {
                "summary": prompt[:80],
                "direction": classification.get("reasoning", ""),
                "codex_prompt": prompt,
                "executor": default_executor,
                "priority": "medium",
                "_fallback_error": str(e),
            }

    def _parse_plan(self, raw: str, task_type: str, default_executor: str) -> dict:
        data = parse_l2_json(raw)
        if "summary" not in data:
            try:
                data = json.loads(raw.strip())
            except json.JSONDecodeError:
                match = re.search(r"\{.*\}", raw, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(0))
                    except json.JSONDecodeError:
                        data = {}

        if not data:
            return {
                "summary": raw[:120],
                "direction": raw,
                "codex_prompt": raw,
                "executor": default_executor,
                "priority": "medium",
            }

        data.setdefault("executor", self._default_executor(task_type, default_executor))
        data.setdefault("summary", "")
        data.setdefault("direction", "")
        data.setdefault("codex_prompt", data.get("direction") or raw)
        return data

    @staticmethod
    def _planner_model(complexity_tier: str) -> str:
        return PLAN_FLASH_MODEL if complexity_tier in {"T0", "T1"} else PLAN_PRO_MODEL

    @staticmethod
    def _default_executor(task_type: str, fallback: str = "codex") -> str:
        if task_type in CURSOR_TYPES:
            return "cursor_queue"
        if task_type in BRAIN_ONLY_TYPES:
            return "brain_only"
        if task_type in RELAY_API_TYPES:
            return "relay_api"
        if task_type in CODEX_TYPES:
            return "codex"
        return fallback

    def _resolve_executor(self, task_type: str, planned: str, routed: str) -> str:
        planned = (planned or "").strip().lower()
        allowed = {"codex", "cursor_queue", "brain_only", "relay_api"}
        if task_type in CURSOR_TYPES:
            return "cursor_queue"
        if task_type in BRAIN_ONLY_TYPES:
            return "brain_only"
        if task_type in CODEX_TYPES and planned in {"brain_only", "relay_api"}:
            return "codex"
        if task_type in RELAY_API_TYPES and planned == "brain_only":
            return routed
        if planned in allowed:
            return planned
        return self._default_executor(task_type, routed)

    def _base_subtask(
        self,
        sub: Subtask,
        task_type: str,
        executor: str,
        plan: dict,
        decision,
        result: str,
        success: bool,
        confidence: float = 0.5,
        cursor_task_id: str | None = None,
        trace_id: str = "",
        model: str | None = None,
        attempts: list[dict] | None = None,
    ) -> SubtaskDispatch:
        return SubtaskDispatch(
            index=sub.index,
            prompt=sub.prompt,
            task_type=task_type,
            executor=executor,
            model=model or (decision.model if executor != "cursor_queue" else "cursor_queue"),
            plan_summary=plan.get("summary", ""),
            direction=plan.get("direction", ""),
            result=result,
            success=success,
            confidence=confidence,
            cursor_task_id=cursor_task_id,
            primary=decision.primary,
            fallback=decision.fallback,
            tier=decision.tier,
            complexity_tier=decision.complexity_tier,
            budget_zone=decision.budget_zone,
            trace_id=trace_id,
            attempts=attempts or [],
        )

    def _dispatch_cursor(
        self,
        sub: Subtask,
        task_type: str,
        plan: dict,
        decision,
        trace_id: str,
    ) -> SubtaskDispatch:
        ct = cursor_push(
            task_type=task_type,
            instruction=sub.prompt,
            context=plan.get("direction", ""),
        )
        result_text = (
            "Queued in Cursor Queue\n"
            f"ID: {ct.id}\n"
            "Run: python scripts/cursor_cli.py pop"
        )
        return self._base_subtask(
            sub,
            task_type,
            "cursor_queue",
            plan,
            decision,
            result_text,
            True,
            cursor_task_id=ct.id,
            trace_id=trace_id,
        )

    async def _dispatch_brain_only(
        self,
        sub: Subtask,
        task_type: str,
        plan: dict,
        decision,
        trace_id: str,
    ) -> SubtaskDispatch:
        return await self._dispatch_provider(
            sub,
            task_type,
            "brain_only",
            plan,
            decision,
            trace_id,
        )

    async def _dispatch_relay_api(
        self,
        sub: Subtask,
        task_type: str,
        plan: dict,
        decision,
        trace_id: str,
    ) -> SubtaskDispatch:
        return await self._dispatch_provider(
            sub,
            task_type,
            "relay_api",
            plan,
            decision,
            trace_id,
        )

    async def _dispatch_provider(
        self,
        sub: Subtask,
        task_type: str,
        executor: str,
        plan: dict,
        decision,
        trace_id: str,
    ) -> SubtaskDispatch:
        prompt = plan.get("codex_prompt") or (
            f"Task: {sub.prompt}\n\nDirection:\n{plan.get('direction', '')}"
        )
        candidates = [
            ModelId.parse(model)
            for model in [decision.primary, *decision.fallback]
            if model != "cursor_queue"
        ]
        service = ExecutionService(
            LiteLLMProvider(),
            RetryPolicy(max_retries=1),
            timeout_seconds=120,
        )
        execution = await service.execute(
            trace_id=TraceId(trace_id),
            prompt=prompt,
            candidates=candidates,
        )
        attempts = [
            {
                "model": attempt.model_id.value,
                "attempt": attempt.attempt,
                "status": attempt.status,
                "action": attempt.action,
                "error_type": attempt.error_type,
                "latency_ms": attempt.latency_ms,
            }
            for attempt in execution.attempts
        ]
        if execution.response:
            return self._base_subtask(
                sub,
                task_type,
                executor,
                plan,
                decision,
                execution.response.content,
                True,
                trace_id=trace_id,
                model=execution.response.model_id.value,
                attempts=attempts,
            )
        return self._base_subtask(
            sub,
            task_type,
            executor,
            plan,
            decision,
            f"[ERROR:{execution.final_error_type}] {execution.outcome}",
            False,
            trace_id=trace_id,
            attempts=attempts,
        )

    async def _dispatch_codex(
        self,
        sub: Subtask,
        task_type: str,
        plan: dict,
        decision,
        workdir: str,
        trace_id: str,
    ) -> SubtaskDispatch:
        codex_prompt = plan.get("codex_prompt") or (
            f"Task: {sub.prompt}\n\nDirection:\n{plan.get('direction', '')}"
        )
        codex_prompt = f"Preferred execution model from router: {decision.model}\n\n{codex_prompt}"

        if not codex_available():
            return self._base_subtask(
                sub,
                task_type,
                "codex",
                plan,
                decision,
                "[ERROR] Codex CLI is unavailable",
                False,
                trace_id=trace_id,
            )

        cx = await run_codex(codex_prompt, workdir=workdir)
        result_text = cx.output if cx.success else f"[ERROR] {cx.error}"
        return self._base_subtask(
            sub,
            task_type,
            "codex",
            plan,
            decision,
            result_text,
            cx.success,
            trace_id=trace_id,
        )

    def _aggregate(
        self,
        subs: list[SubtaskDispatch],
        steps: list[str],
        timeline: list[DispatchStep],
        workdir: str,
        decomposed: bool,
        trace_id: str,
    ) -> DispatchResult:
        if not subs:
            return DispatchResult(
                trace_id=trace_id,
                task_type="uncertain",
                selected_executor="none",
                reason="No subtasks were produced",
                steps=steps,
                timeline=timeline,
                result="No dispatch result was generated.",
                cost_level="low",
                workdir=workdir,
                codex_available=codex_available(),
                decomposed=decomposed,
            )

        types = [s.task_type for s in subs]
        main_type = max(set(types), key=types.count)
        executors = [s.executor for s in subs]
        main_exec = max(set(executors), key=executors.count)

        if len(subs) == 1:
            body = subs[0].result
        else:
            body = "\n---\n".join(
                (
                    f"### Subtask {s.index}: {s.task_type} -> {s.executor}\n"
                    f"**Plan:** {s.plan_summary}\n\n{s.result}\n"
                )
                for s in subs
            )

        cost_map = {
            "architecture": "high",
            "system_design": "high",
            "deep_reasoning": "high",
            "implementation": "medium",
            "debugging": "medium",
            "refactor": "medium",
            "boilerplate": "low",
            "bulk_generation": "low",
            "data_processing": "low",
            "code_patch": "low",
            "file_edit": "low",
            "uncertain": "medium",
        }
        levels = [cost_map.get(t, "medium") for t in types]
        cost_order = {"low": 0, "medium": 1, "high": 2}
        main_cost = max(levels, key=lambda x: cost_order.get(x, 0))

        return DispatchResult(
            trace_id=trace_id,
            task_type=main_type,
            selected_executor=main_exec,
            reason="DeepSeek planned and dispatcher routed to the selected executor",
            steps=steps,
            timeline=timeline,
            result=body,
            cost_level=main_cost,
            workdir=workdir,
            subtasks=subs,
            codex_available=codex_available(),
            decomposed=decomposed,
        )


async def dispatch_prompt(prompt: str, *, workdir: str | Path = ".") -> dict:
    """Convenience JSON entry point for POST /api/route."""
    dispatcher = TaskDispatcher()
    result = await dispatcher.dispatch(prompt, workdir=workdir)
    selected_model = result.subtasks[0].model if result.subtasks else result.selected_executor
    return {
        "trace_id": result.trace_id,
        "task_type": result.task_type,
        "selected_executor": result.selected_executor,
        "selected_model": selected_model,
        "reason": result.reason,
        "steps": result.steps,
        "timeline": [
            {"phase": t.phase, "detail": t.detail, "status": t.status}
            for t in result.timeline
        ],
        "result": result.result,
        "cost_level": result.cost_level,
        "workdir": result.workdir,
        "decomposed": result.decomposed,
        "subtask_count": len(result.subtasks),
        "codex_available": result.codex_available,
        "primary": result.subtasks[0].primary if result.subtasks else selected_model,
        "fallback": result.subtasks[0].fallback if result.subtasks else [],
        "executor": result.selected_executor,
        "tier": result.subtasks[0].tier if result.subtasks else "",
        "complexity_tier": result.subtasks[0].complexity_tier if result.subtasks else "",
        "subtasks": [
            {
                "index": s.index,
                "prompt": s.prompt,
                "task_type": s.task_type,
                "executor": s.executor,
                "model": s.model,
                "primary": s.primary,
                "fallback": s.fallback,
                "tier": s.tier,
                "complexity_tier": s.complexity_tier,
                "budget_zone": s.budget_zone,
                "plan_summary": s.plan_summary,
                "direction": s.direction,
                "result": s.result,
                "success": s.success,
                "cursor_task_id": s.cursor_task_id,
                "trace_id": s.trace_id,
                "attempts": s.attempts,
            }
            for s in result.subtasks
        ],
    }


if __name__ == "__main__":
    import asyncio
    import sys

    p = sys.argv[1] if len(sys.argv) > 1 else "write a hello world function"
    wd = sys.argv[2] if len(sys.argv) > 2 else "."
    out = asyncio.run(dispatch_prompt(p, workdir=wd))
    print(json.dumps(out, ensure_ascii=False, indent=2))
