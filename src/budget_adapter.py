"""预算状态适配 — 从 llm-router Budget Oracle 读取 pressure，供 routing_table 使用。"""

from __future__ import annotations

import asyncio

_DEFAULT_PROVIDERS = ("anthropic", "openai", "deepseek")


async def get_budget_ratio(providers: tuple[str, ...] = _DEFAULT_PROVIDERS) -> float:
    """返回 0.0–1.0 预算消耗比例（取各 provider 最大 pressure）。

    llm-router 不可用时静默返回 0.0（green zone）。
    """
    try:
        from llm_router.budget import get_budget_state

        pressures: list[float] = []
        for provider in providers:
            state = await get_budget_state(provider)
            pressures.append(float(state.pressure))
        return max(pressures) if pressures else 0.0
    except Exception:
        return 0.0


def get_budget_ratio_sync(providers: tuple[str, ...] = _DEFAULT_PROVIDERS) -> float:
    """同步包装，供非 async 上下文使用。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(get_budget_ratio(providers))
    # 已在 event loop 内 — 不应阻塞；调用方应使用 async 版本
    if loop.is_running():
        return 0.0
    return asyncio.run(get_budget_ratio(providers))
