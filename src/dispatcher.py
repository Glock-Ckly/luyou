"""
Dispatcher — 纯任务分发器

DeepSeek（大脑）: 拆分 → 分类 → 规划方向
Codex / Cursor Queue: 按规划执行，本模块不介入执行细节

架构:
  Prompt → Decomposer(DeepSeek) → Classify(L1/L2 DeepSeek) → Plan(DeepSeek)
       → Route → Codex exec | Cursor Queue | brain_only
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from l1_classifier import classify_l1
from l2_classifier import classify_l2, parse_l2_json
from routing_table import route, CostLevel
from task_decomposer import decompose, Subtask, DecomposerResult
from cursor_queue import push as cursor_push
from codex_executor import run_codex, codex_available
from relay_config import apply_relay_env
from budget_adapter import get_budget_ratio

apply_relay_env()

_PLANNER_PROMPT = (Path(__file__).parent / "prompts" / "planner.txt").read_text(
    encoding="utf-8"
).strip()

CURSOR_TYPES = {"code_patch", "file_edit"}
CODEX_TYPES = {
    "implementation", "debugging", "refactor",
    "boilerplate", "bulk_generation", "data_processing", "uncertain",
}
BRAIN_ONLY_TYPES = {"architecture", "system_design", "deep_reasoning"}


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


@dataclass
class DispatchResult:
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
    """只分发，不执行编码逻辑。"""

    def __init__(self, l1_threshold: float = 0.7):
        self.l1_threshold = l1_threshold

    async def dispatch(
        self,
        prompt: str,
        *,
        workdir: str | Path,
    ) -> DispatchResult:
        work = str(Path(workdir).resolve())
        timeline: list[DispatchStep] = []
        steps: list[str] = []
        sub_dispatches: list[SubtaskDispatch] = []

        # 1. 拆分
        steps.append("decompose")
        timeline.append(DispatchStep("decompose", "DeepSeek 分析是否拆分任务", "running"))
        decomp = await self._decompose(prompt)
        timeline[-1] = DispatchStep(
            "decompose",
            f"{'已拆分' if decomp.split else '单任务'} · {len(decomp.subtasks)} 个子任务",
            "done",
        )

        budget_ratio = await get_budget_ratio()

        for sub in decomp.subtasks:
            # 2. 分类
            steps.append("classify")
            timeline.append(DispatchStep(
                "classify",
                f"子任务 {sub.index}: L1/L2 分类",
                "running",
            ))
            classification = await self._classify(sub)
            task_type = classification["task_type"]
            timeline[-1] = DispatchStep(
                "classify",
                f"→ {task_type} (conf {classification.get('confidence', 0):.2f}, {classification.get('source', '?')})",
                "done",
            )

            # 3. 路由
            steps.append("route")
            decision = route(
                task_type=task_type,
                complexity=classification.get("complexity", 3),
                budget_ratio=budget_ratio,
            )
            timeline.append(DispatchStep(
                "route",
                f"路由表 → {decision.model}",
                "done",
            ))

            # 4. DeepSeek 规划
            steps.append("plan")
            timeline.append(DispatchStep("plan", "DeepSeek 生成执行方向", "running"))
            plan = await self._plan(sub.prompt, task_type, classification)
            executor = self._resolve_executor(task_type, plan.get("executor", ""))
            timeline[-1] = DispatchStep(
                "plan",
                f"{plan.get('summary', '')[:60]} → {executor}",
                "done",
            )

            # 5. 分发执行
            steps.append("dispatch")
            timeline.append(DispatchStep("dispatch", f"交给 {executor}", "running"))

            if executor == "cursor_queue":
                ct = cursor_push(
                    task_type=task_type,
                    instruction=sub.prompt,
                    context=plan.get("direction", ""),
                )
                result_text = (
                    f"已入队 Cursor Queue\n"
                    f"ID: {ct.id}\n"
                    f"运行: python scripts/cursor_cli.py pop"
                )
                sub_dispatches.append(SubtaskDispatch(
                    index=sub.index,
                    prompt=sub.prompt,
                    task_type=task_type,
                    executor="cursor_queue",
                    model="cursor_queue",
                    plan_summary=plan.get("summary", ""),
                    direction=plan.get("direction", ""),
                    result=result_text,
                    success=True,
                    confidence=classification.get("confidence", 0.5),
                    cursor_task_id=ct.id,
                ))
                timeline[-1] = DispatchStep("dispatch", f"Cursor Queue · {ct.id}", "done")

            elif executor == "brain_only":
                result_text = (
                    f"## 方向\n{plan.get('direction', '')}\n\n"
                    f"## 说明\n{plan.get('codex_prompt', plan.get('summary', ''))}"
                )
                sub_dispatches.append(SubtaskDispatch(
                    index=sub.index,
                    prompt=sub.prompt,
                    task_type=task_type,
                    executor="brain_only",
                    model="deepseek/deepseek-chat",
                    plan_summary=plan.get("summary", ""),
                    direction=plan.get("direction", ""),
                    result=result_text,
                    success=True,
                    confidence=classification.get("confidence", 0.5),
                ))
                timeline[-1] = DispatchStep("dispatch", "仅规划，未调用 Codex", "skipped")

            else:  # codex
                codex_prompt = plan.get("codex_prompt") or (
                    f"Task: {sub.prompt}\n\nDirection:\n{plan.get('direction', '')}"
                )
                if not codex_available():
                    result_text = "[ERROR] Codex CLI 不可用"
                    success = False
                    timeline[-1] = DispatchStep("dispatch", "Codex 不可用", "error")
                else:
                    cx = await run_codex(codex_prompt, workdir=work)
                    result_text = cx.output if cx.success else f"[ERROR] {cx.error}"
                    success = cx.success
                    timeline[-1] = DispatchStep(
                        "dispatch",
                        f"Codex exit {cx.exit_code}",
                        "done" if success else "error",
                    )

                sub_dispatches.append(SubtaskDispatch(
                    index=sub.index,
                    prompt=sub.prompt,
                    task_type=task_type,
                    executor="codex",
                    model="codex",
                    plan_summary=plan.get("summary", ""),
                    direction=plan.get("direction", ""),
                    result=result_text,
                    success=success,
                    confidence=classification.get("confidence", 0.5),
                ))

        steps.append("aggregate")
        return self._aggregate(sub_dispatches, steps, timeline, work, decomp.split)

    async def _decompose(self, prompt: str) -> DecomposerResult:
        from relay_llm import call_llm

        async def _call(model, messages, **kwargs):
            return await call_llm(model=model, messages=messages, **kwargs)

        return await decompose(prompt, call_llm=_call)

    async def _classify(self, subtask: Subtask) -> dict:
        if subtask.type_hint:
            return {
                "task_type": subtask.type_hint,
                "complexity": 3,
                "confidence": 0.8,
                "reasoning": f"decomposer type_hint: {subtask.type_hint}",
                "source": "decomposer",
            }

        l1 = classify_l1(subtask.prompt, confidence_threshold=self.l1_threshold)
        if l1 is not None:
            return {
                "task_type": l1.task_type,
                "complexity": 3,
                "confidence": l1.confidence,
                "reasoning": l1.reasoning,
                "source": "L1",
            }

        return await classify_l2(subtask.prompt)

    async def _plan(self, prompt: str, task_type: str, classification: dict) -> dict:
        from relay_llm import call_llm

        user = (
            f"Task type: {task_type}\n"
            f"Classification: {json.dumps(classification, ensure_ascii=False)}\n"
            f"User task:\n{prompt}"
        )
        try:
            resp = await call_llm(
                model="deepseek/deepseek-chat",
                messages=[
                    {"role": "system", "content": _PLANNER_PROMPT},
                    {"role": "user", "content": user},
                ],
                temperature=0.0,
                max_tokens=1024,
            )
            return self._parse_plan(resp.content, task_type)
        except Exception as e:
            return {
                "summary": prompt[:80],
                "direction": classification.get("reasoning", ""),
                "codex_prompt": prompt,
                "executor": self._default_executor(task_type),
                "priority": "medium",
                "_fallback_error": str(e),
            }

    def _parse_plan(self, raw: str, task_type: str) -> dict:
        data = parse_l2_json(raw)  # same JSON extraction
        if "summary" not in data:
            # try planner-specific keys
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
                "executor": self._default_executor(task_type),
                "priority": "medium",
            }

        data.setdefault("executor", self._default_executor(task_type))
        data.setdefault("summary", "")
        data.setdefault("direction", "")
        data.setdefault("codex_prompt", data.get("direction") or raw)
        return data

    @staticmethod
    def _default_executor(task_type: str) -> str:
        if task_type in CURSOR_TYPES:
            return "cursor_queue"
        if task_type in BRAIN_ONLY_TYPES:
            return "brain_only"
        return "codex"

    def _resolve_executor(self, task_type: str, planned: str) -> str:
        planned = (planned or "").strip().lower()
        if task_type in CURSOR_TYPES:
            return "cursor_queue"
        if planned in ("codex", "cursor_queue", "brain_only"):
            if planned == "brain_only" and task_type in CODEX_TYPES:
                return "codex"
            return planned
        return self._default_executor(task_type)

    def _aggregate(
        self,
        subs: list[SubtaskDispatch],
        steps: list[str],
        timeline: list[DispatchStep],
        workdir: str,
        decomposed: bool,
    ) -> DispatchResult:
        if not subs:
            return DispatchResult(
                task_type="uncertain",
                selected_executor="none",
                reason="无子任务",
                steps=steps,
                timeline=timeline,
                result="未生成任何分发结果。",
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
            parts = []
            for s in subs:
                parts.append(
                    f"### 子任务 {s.index}: {s.task_type} → {s.executor}\n"
                    f"**规划:** {s.plan_summary}\n\n{s.result}\n"
                )
            body = "\n---\n".join(parts)

        cost_map = {
            "architecture": "medium", "system_design": "medium",
            "deep_reasoning": "high", "implementation": "medium",
            "debugging": "medium", "refactor": "medium",
            "boilerplate": "low", "bulk_generation": "low",
            "data_processing": "low", "code_patch": "low",
            "file_edit": "low", "uncertain": "medium",
        }
        levels = [cost_map.get(t, "medium") for t in types]
        cost_order = {"low": 0, "medium": 1, "high": 2}
        main_cost = max(levels, key=lambda x: cost_order.get(x, 0))

        return DispatchResult(
            task_type=main_type,
            selected_executor=main_exec,
            reason="DeepSeek 规划 → 分发执行（本模块不介入编码）",
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
    """便捷入口 → JSON dict（供 dashboard API 使用）。"""
    d = TaskDispatcher()
    r = await d.dispatch(prompt, workdir=workdir)
    return {
        "task_type": r.task_type,
        "selected_executor": r.selected_executor,
        "selected_model": r.selected_executor,
        "reason": r.reason,
        "steps": r.steps,
        "timeline": [
            {"phase": t.phase, "detail": t.detail, "status": t.status}
            for t in r.timeline
        ],
        "result": r.result,
        "cost_level": r.cost_level,
        "workdir": r.workdir,
        "decomposed": r.decomposed,
        "subtask_count": len(r.subtasks),
        "codex_available": r.codex_available,
        "subtasks": [
            {
                "index": s.index,
                "prompt": s.prompt,
                "task_type": s.task_type,
                "executor": s.executor,
                "plan_summary": s.plan_summary,
                "direction": s.direction,
                "result": s.result,
                "success": s.success,
                "cursor_task_id": s.cursor_task_id,
            }
            for s in r.subtasks
        ],
    }


if __name__ == "__main__":
    import asyncio
    import sys

    p = sys.argv[1] if len(sys.argv) > 1 else "写一个 hello world 函数"
    wd = sys.argv[2] if len(sys.argv) > 2 else "."
    out = asyncio.run(dispatch_prompt(p, workdir=wd))
    print(json.dumps(out, ensure_ascii=False, indent=2))
