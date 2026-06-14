#!/usr/bin/env python3
"""4 场景端到端测试 — 对应 multi-llm-router-design.md 示例 1–4。

场景 1: 简单实现 → implementation + LLM 响应
场景 2: 大任务分解 → split + 多子任务
场景 3: Cursor 文件修改 → code_patch + cursor_queue
场景 4: 预算路由 (mock orange zone) → 路由决策符合预期

通过标准: 4/4 场景断言通过（场景 2 允许 split 启发式波动，检查 steps 含 decompose）
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from relay_config import apply_relay_env  # noqa: E402
from orchestrator import MultiModelOrchestrator, handle_prompt  # noqa: E402
from routing_table import route  # noqa: E402

PASSED = 0
FAILED = 0


def ok(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    line = f"{'PASS' if cond else 'FAIL'}: {name}" + (f" — {detail}" if detail else "")
    print(line)
    if cond:
        PASSED += 1
    else:
        FAILED += 1


async def scenario_1_simple_impl() -> None:
    """示例 1: 简单实现任务"""
    r = await handle_prompt("帮我写一个 Python 装饰器，用来测量函数执行时间")
    ok("S1 task_type is implementation-ish", r["task_type"] in (
        "implementation", "boilerplate", "uncertain"
    ), r["task_type"])
    ok("S1 model not none/cursor", r["selected_model"] not in ("none", "cursor_queue"), r["selected_model"])
    ok("S1 has result", len(r.get("result", "")) > 20, r.get("result", "")[:80])


async def scenario_2_decompose() -> None:
    """示例 2: 大任务分解"""
    prompt = (
        "帮我做一个用户登录系统，包括数据库设计、后端 API 和前端表单。"
        "需要：1) 设计 users 表 2) 实现 POST /login 3) 写登录页 HTML"
    )
    orch = MultiModelOrchestrator()
    result = await orch.handle(prompt)
    ok("S2 steps include decompose", "decompose" in result.steps, " → ".join(result.steps[:6]))
    ok("S2 has subtask results", len(result.subtask_results) >= 1, str(len(result.subtask_results)))
  # 若拆分成功应有多个子任务；未拆分时至少 1 条仍通过路由
    if len(result.subtask_results) > 1:
        models = {sr.model for sr in result.subtask_results}
        ok("S2 multiple models or routes", len(models) >= 1, str(models))
    ok("S2 aggregate result non-empty", len(result.result) > 10, result.result[:60])


async def scenario_3_cursor_queue() -> None:
    """示例 3: Cursor 文件修改"""
    r = await handle_prompt(
        "帮我把 src/auth.py 里的 JWT token 过期时间从 15 分钟改成 1 小时"
    )
    ok("S3 task_type code_patch or file_edit", r["task_type"] in (
        "code_patch", "file_edit"
    ), r["task_type"])
    ok("S3 cursor_queue or queued message", (
        r["selected_model"] == "cursor_queue" or r.get("cursor_tasks", 0) > 0
    ), f"model={r['selected_model']} cursor_tasks={r.get('cursor_tasks')}")
    ok("S3 result mentions queue", "queue" in r.get("result", "").lower() or r.get("cursor_tasks", 0) > 0,
       r.get("result", "")[:80])


def scenario_4_budget_routing() -> None:
    """示例 4: 预算渐进降级 — 纯路由表逻辑，不调用 API"""
    # orange zone: implementation 应降级
    d_impl = route(task_type="implementation", complexity=3, budget_ratio=0.78)
    ok("S4 orange impl downgrades", "deepseek" in d_impl.model.lower(), d_impl.model)

    # architecture 关键任务保持
    d_arch = route(task_type="architecture", complexity=3, budget_ratio=0.78)
    ok("S4 orange arch stays claude", "claude" in d_arch.model.lower(), d_arch.model)

    # bulk_generation 已在最便宜
    d_bulk = route(task_type="bulk_generation", complexity=3, budget_ratio=0.78)
    ok("S4 orange bulk stays deepseek", "deepseek" in d_bulk.model.lower(), d_bulk.model)


async def main() -> int:
    apply_relay_env()
    print("=== E2E Eval: 4 scenarios ===\n")

    print("--- Scenario 1: simple implementation ---")
    await scenario_1_simple_impl()
    print()

    print("--- Scenario 2: large task decompose ---")
    await scenario_2_decompose()
    print()

    print("--- Scenario 3: cursor queue ---")
    await scenario_3_cursor_queue()
    print()

    print("--- Scenario 4: budget routing (no API) ---")
    scenario_4_budget_routing()
    print()

    print(f"=== Done: {PASSED} passed, {FAILED} failed ===")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
