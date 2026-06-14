"""
中转站 LLM 调用薄封装 — 直接走 LiteLLM，避免 llm-router 缺 standard.yaml 的导入错误。

orchestrator / task_decomposer / smoke 测试统一使用本模块的 call_llm。
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import litellm

from relay_config import apply_relay_env, resolve_model

apply_relay_env()
litellm.suppress_debug_info = True


@dataclass
class RelayLLMResponse:
    content: str
    model: str
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


async def call_llm(
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float | None = 0.0,
    max_tokens: int | None = 256,
    **kwargs,
) -> RelayLLMResponse:
    """调用 LiteLLM acompletion，模型名经 relay_models.yaml 映射。"""
    resolved = resolve_model(model)
    model_name = resolved.split("/", 1)[-1] if "/" in resolved else resolved
    if model_name.startswith(("o1", "o3", "o4")):
        temperature = 1

    req: dict = {
        "model": resolved,
        "messages": messages,
        "temperature": temperature if temperature is not None else 0.0,
        "timeout": 120,
    }
    if max_tokens and not resolved.startswith("ollama/"):
        req["max_tokens"] = max_tokens

    start = time.monotonic()
    response = await litellm.acompletion(**req)
    elapsed_ms = (time.monotonic() - start) * 1000

    msg = response.choices[0].message
    content = msg.content or getattr(msg, "reasoning", "") or ""
    if not str(content).strip():
        raise RuntimeError(f"Empty response from {resolved}")

    usage = response.usage
    try:
        cost = float(litellm.completion_cost(completion_response=response) or 0)
    except Exception:
        cost = 0.0

    return RelayLLMResponse(
        content=str(content),
        model=resolved,
        cost_usd=cost,
        input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
    )
