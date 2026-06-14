"""
Orchestrator — 中央编排器

串联全流程:
  1. TaskDecomposer → 拆分大任务
  2. L1 Heuristic Classifier → 关键词快筛
  3. L2 LLM Classifier (DeepSeek) → 精确分类
  4. Routing Table → 模型选择 + 复杂度修正 + 预算控制
  5. Model Execution → 调用 llm-router providers
  6. Cursor Queue → code_patch/file_edit 任务入队
  7. Response Validator → 后验校验
  8. Response Aggregator → 合并输出

依赖: llm-router (providers.call_llm, budget, health)
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path

from l1_classifier import classify_l1, L1Result
from routing_table import (
    route,
    RoutingDecision,
    TaskType,
    CostLevel,
    FALLBACK_CHAINS,
    CRITICAL_TASKS,
)
from response_validator import validate, ValidationStatus
from cursor_queue import push as cursor_push
from task_decomposer import decompose, Subtask, DecomposerResult
from relay_config import apply_relay_env, resolve_model
from budget_adapter import get_budget_ratio
from l2_classifier import classify_l2

# 在任何 llm_router 导入之前注入中转站环境变量
apply_relay_env()


@dataclass
class SubtaskResult:
    """单个子任务的执行结果"""
    index: int
    prompt: str
    task_type: str
    model: str
    cost_level: str
    response_text: str
    confidence: float
    validated: bool
    cost_usd: float = 0.0


@dataclass
class OrchestratorResult:
    """编排器最终输出"""
    task_type: str
    selected_model: str
    reason: str
    steps: list[str]
    result: str
    cost_level: str
    subtask_results: list[SubtaskResult] = field(default_factory=list)
    cursor_tasks: list[dict] = field(default_factory=list)
    total_cost_usd: float = 0.0


class MultiModelOrchestrator:
    """多模型路由编排器。

    不修改 llm-router 源码，作为 wrapper 导入 llm-router 的基础设施。
    """

    def __init__(
        self,
        l1_threshold: float = 0.7,
        l2_model: str = "deepseek/deepseek-chat",
    ):
        self.l1_threshold = l1_threshold
        self.l2_model = l2_model

    async def handle(self, prompt: str) -> OrchestratorResult:
        """主入口: 处理一次用户请求。

        Args:
            prompt: 用户自然语言输入

        Returns:
            OrchestratorResult — 统一 JSON 格式
        """
        steps = []

        # ── Step 1: 任务分解 ──────────────────────────
        steps.append("decompose")
        decomposer_result = await self._decompose(prompt)

        # ── Step 2-4: 对每个子任务分类+路由+执行 ──────
        results: list[SubtaskResult] = []
        cursor_tasks: list[dict] = []
        total_cost = 0.0

        for subtask in decomposer_result.subtasks:
            # Step 2: 分类
            steps.append("classify")
            classification = await self._classify(subtask)

            # Step 3: 路由
            steps.append("route")
            budget_ratio = await self._get_budget_ratio()
            decision = route(
                task_type=classification["task_type"],
                complexity=classification.get("complexity", 3),
                budget_ratio=budget_ratio,
            )

            # Step 4: 执行
            if decision.model == "cursor_queue":
                # → Cursor Queue
                ct = cursor_push(
                    task_type=decision.task_type,
                    instruction=subtask.prompt,
                    context=classification.get("reasoning", ""),
                )
                cursor_tasks.append({
                    "id": ct.id,
                    "type": ct.type,
                    "instruction": ct.instruction,
                })
                steps.append("cursor_queue")

                results.append(SubtaskResult(
                    index=subtask.index,
                    prompt=subtask.prompt,
                    task_type=decision.task_type,
                    model="cursor_queue",
                    cost_level="low",
                    response_text=f"Task queued. Run `cursor-pop` to retrieve (id: {ct.id})",
                    confidence=classification.get("confidence", 0.5),
                    validated=True,
                ))
                continue

            # → LLM API
            steps.append("execute")
            exec_result = await self._execute(
                model=decision.model,
                prompt=subtask.prompt,
                fallback_chain=decision.fallback_chain,
            )

            # Step 5: 后验校验
            steps.append("validate")
            validation = validate(exec_result["text"])
            if validation.status == ValidationStatus.RETRY_SAME:
                exec_result = await self._execute(
                    model=decision.model,
                    prompt=subtask.prompt,
                    fallback_chain=decision.fallback_chain,
                )
                validation = validate(exec_result["text"])
            elif validation.status == ValidationStatus.RETRY_UPGRADE:
                upgrade = decision.fallback_chain[0] if decision.fallback_chain else decision.model
                exec_result = await self._execute(
                    model=upgrade,
                    prompt=subtask.prompt,
                    fallback_chain=decision.fallback_chain,
                )

            total_cost += exec_result.get("cost_usd", 0.0)

            results.append(SubtaskResult(
                index=subtask.index,
                prompt=subtask.prompt,
                task_type=decision.task_type,
                model=exec_result.get("model", decision.model),
                cost_level=decision.cost_level.value,
                response_text=exec_result["text"],
                confidence=classification.get("confidence", 0.5),
                validated=validation.status == ValidationStatus.PASS,
                cost_usd=exec_result.get("cost_usd", 0.0),
            ))

        # ── Step 6: 聚合 ──────────────────────────────
        steps.append("aggregate")
        return self._aggregate(results, cursor_tasks, steps, total_cost)

    # ── Private methods ──────────────────────────────────

    async def _decompose(self, prompt: str) -> DecomposerResult:
        """任务分解"""
        from relay_llm import call_llm

        async def _call(model, messages, **kwargs):
            return await call_llm(model=model, messages=messages, **kwargs)

        return await decompose(prompt, call_llm=_call)

    async def _classify(self, subtask: Subtask) -> dict:
        """两级分类"""
        # L1: 关键词
        if subtask.type_hint:
            # Decomposer 已经给了 type_hint → 直接使用
            return {
                "task_type": subtask.type_hint,
                "complexity": 3,
                "confidence": 0.8,
                "reasoning": f"inherited from decomposer type_hint: {subtask.type_hint}",
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

        # L2: LLM (DeepSeek)
        return await self._classify_l2(subtask.prompt)

    async def _classify_l2(self, prompt: str) -> dict:
        """L2 LLM 分类器"""
        return await classify_l2(prompt, l2_model=self.l2_model)

    async def _execute(
        self,
        model: str,
        prompt: str,
        fallback_chain: list[str],
        max_retries: int = 2,
    ) -> dict:
        """调用 LLM API，失败沿降级链回退"""
        from relay_llm import call_llm

        chain = [resolve_model(model)] + [
            resolve_model(m) for m in fallback_chain if m != model and m != "cursor_queue"
        ]
        last_error = None

        for attempt, m in enumerate(chain[:max_retries + 1]):
            try:
                resp = await call_llm(
                    model=m,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=4096,
                )
                return {
                    "text": resp.content,
                    "model": m,
                    "cost_usd": resp.cost_usd,
                    "attempt": attempt,
                }
            except Exception as e:
                last_error = e
                continue

        # 全部失败
        return {
            "text": f"[ERROR] All models failed. Last error: {last_error}",
            "model": "none",
            "cost_usd": 0.0,
            "attempt": len(chain),
        }

    async def _get_budget_ratio(self) -> float:
        """获取预算消耗比例 (0.0-1.0)"""
        return await get_budget_ratio()

    def _aggregate(
        self,
        results: list[SubtaskResult],
        cursor_tasks: list[dict],
        steps: list[str],
        total_cost: float,
    ) -> OrchestratorResult:
        """聚合子任务结果"""
        if not results:
            return OrchestratorResult(
                task_type="uncertain",
                selected_model="none",
                reason="No results",
                steps=steps,
                result="No output generated.",
                cost_level="low",
            )

        # 主任务类型: 取第一个或多数
        types = [r.task_type for r in results]
        main_type = max(set(types), key=types.count) if types else "uncertain"

        # 主模型: 取第一个非 cursor 的
        models = [r.model for r in results if r.model != "cursor_queue"]
        main_model = models[0] if models else "cursor_queue"

        # 成本级别: 取最高
        cost_order = {"low": 0, "medium": 1, "high": 2}
        max_cost = max((cost_order.get(r.cost_level, 0) for r in results), default=0)
        main_cost = {v: k for k, v in cost_order.items()}.get(max_cost, "low")

        # 拼接结果
        if len(results) == 1:
            result_text = results[0].response_text
        else:
            parts = []
            for r in results:
                parts.append(
                    f"## Subtask {r.index}: {r.task_type} → {r.model}\n\n"
                    f"{r.response_text}\n"
                )
            result_text = "\n---\n".join(parts)

        # Cursor tasks
        if cursor_tasks:
            ct_text = "\n\n**Cursor Queue Tasks:**\n" + "\n".join(
                f"- [{t['id']}] {t['type']}: {t['instruction'][:80]}"
                for t in cursor_tasks
            )
            result_text += ct_text

        return OrchestratorResult(
            task_type=main_type,
            selected_model=main_model,
            reason=f"classified via {'+'.join(steps)}",
            steps=steps,
            result=result_text,
            cost_level=main_cost,
            subtask_results=results,
            cursor_tasks=cursor_tasks,
            total_cost_usd=total_cost,
        )

    @staticmethod
    def _parse_json(raw: str) -> dict:
        """4-tier JSON 解析"""
        import re

        try:
            return json.loads(raw.strip())
        except json.JSONDecodeError:
            pass

        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        match = re.search(r"\{[^{}]*\}", raw)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        # Truncated — extract fields
        result = {}
        for key in ("task_type", "complexity", "confidence", "reasoning"):
            match = re.search(rf'"{key}"\s*:\s*"([^"]*)"', raw)
            if match:
                result[key] = match.group(1)
            else:
                match = re.search(rf'"{key}"\s*:\s*([\d.]+)', raw)
                if match:
                    result[key] = float(match.group(1))
        return result if "task_type" in result else {"task_type": "uncertain"}

async def handle_prompt(prompt: str) -> dict:
    """便捷入口: 输入 prompt → 输出 JSON dict"""
    orch = MultiModelOrchestrator()
    result = await orch.handle(prompt)
    return {
        "task_type": result.task_type,
        "selected_model": result.selected_model,
        "reason": result.reason,
        "steps": result.steps,
        "result": result.result,
        "cost_level": result.cost_level,
        "subtask_count": len(result.subtask_results),
        "cursor_tasks": len(result.cursor_tasks),
        "total_cost_usd": result.total_cost_usd,
    }
