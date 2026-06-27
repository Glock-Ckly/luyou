"""
TaskDecomposer — 大任务拆分模块

判断用户 prompt 是否需要拆分为多个子任务。
用 DeepSeek (最便宜) 做拆分决策。

算法:
  1. Prompt > 500 字符 → 考虑拆分
  2. Prompt 含多个独立步骤 → 考虑拆分
  3. 调 DeepSeek 输出子任务 JSON

输出格式:
  {"split": false}  或
  {"split": true, "subtasks": [{"prompt": "...", "type_hint": "architecture|..."}, ...]}
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DECOMPOSER_PROMPT = (Path(__file__).parent / "prompts" / "decomposer.txt").read_text(
    encoding="utf-8"
).strip()

_TYPE_HINT_ALIASES = {
    "testing": "bulk_generation",
    "test": "bulk_generation",
    "tests": "bulk_generation",
    "unit_test": "bulk_generation",
    "system_design": "architecture",
}


@dataclass
class Subtask:
    """拆分后的子任务"""
    prompt: str
    type_hint: str | None = None
    index: int = 0


@dataclass
class DecomposerResult:
    """拆分结果"""
    split: bool
    subtasks: list[Subtask] = field(default_factory=list)
    reasoning: str = ""
    model_used: str = "deepseek/deepseek-v4-flash"
    cost_usd: float = 0.0


def _should_consider_split(prompt: str) -> bool:
    """快速启发式: 是否需要考虑拆分"""
    if len(prompt) > 500:
        return True
    # 含编号列表
    if any(marker in prompt for marker in ["1.", "2.", "3.",
                                             "1)", "2)", "3)",
                                             "1、", "2、", "3、",
                                             "第一步", "第二步",
                                             "first", "second", "third"]):
        return True
    # 含多任务标记
    if "；" in prompt or "。然后" in prompt or "。接着" in prompt:
        return True
    if "and also" in prompt.lower() or "additionally" in prompt.lower():
        return True
    if "先" in prompt and "再" in prompt:
        return True
    return False


async def decompose(
    prompt: str,
    call_llm,  # async fn(model, messages, **kwargs) → LLMResponse
    force: bool = False,
) -> DecomposerResult:
    """尝试拆分大任务。

    Args:
        prompt: 用户输入
        call_llm: LLM 调用函数 (注入依赖)
        force: 强制拆分 (跳过启发式)

    Returns:
        DecomposerResult
    """
    if not force and not _should_consider_split(prompt):
        return DecomposerResult(split=False, subtasks=[Subtask(prompt=prompt, index=0)])

    messages = [
        {"role": "system", "content": DECOMPOSER_PROMPT},
        {"role": "user", "content": prompt},
    ]

    try:
        resp = await call_llm(
            model="deepseek/deepseek-v4-flash",
            messages=messages,
            temperature=0.0,
            max_tokens=1024,
        )

        data = await _parse_decomposer_response(resp, prompt, messages, call_llm, force)
        return _result_from_data(data, prompt)

    except Exception:
        # 拆分失败 → 不拆，整条发给路由器
        return DecomposerResult(split=False, subtasks=[Subtask(prompt=prompt, index=0)])


async def _parse_decomposer_response(resp, prompt: str, messages: list, call_llm, force: bool) -> dict:
    """解析 LLM 响应；force 模式下 split=false 时重试一次。"""
    raw = resp.content
    data = _parse_json(raw)
    cost = resp.cost_usd if hasattr(resp, "cost_usd") else 0.0

    if force and not data.get("split") and _should_consider_split(prompt):
        retry_messages = messages + [
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": (
                    "This is a multi-step project with numbered stages. "
                    "You MUST return split=true with at least 2 subtasks. "
                    "Return ONLY the JSON object."
                ),
            },
        ]
        retry = await call_llm(
            model="deepseek/deepseek-v4-flash",
            messages=retry_messages,
            temperature=0.0,
            max_tokens=1024,
        )
        data = _parse_json(retry.content)
        if hasattr(retry, "cost_usd"):
            cost += retry.cost_usd

    data["_cost_usd"] = cost
    return data


def _result_from_data(data: dict, prompt: str) -> DecomposerResult:
    """从解析后的 dict 构建 DecomposerResult。"""
    cost = data.get("_cost_usd", 0.0)
    if not data.get("split"):
        return DecomposerResult(
            split=False,
            subtasks=[Subtask(prompt=prompt, index=0)],
            reasoning=data.get("reasoning", ""),
            model_used="deepseek/deepseek-v4-flash",
            cost_usd=cost,
        )

    subtasks = []
    for i, st in enumerate(data.get("subtasks", [])):
        hint = st.get("type_hint")
        if hint:
            hint = _TYPE_HINT_ALIASES.get(hint, hint)
        subtasks.append(Subtask(
            prompt=st.get("prompt", ""),
            type_hint=hint,
            index=i,
        ))

    return DecomposerResult(
        split=True,
        subtasks=subtasks,
        reasoning=data.get("reasoning", ""),
        model_used="deepseek/deepseek-v4-flash",
        cost_usd=cost,
    )


def _parse_json(raw: str) -> dict:
    """4-tier JSON 解析 (复用 llm-router _parse_classification 策略)

    1. 直接解析
    2. markdown fence 提取
    3. 正则 {.*} 提取
    4. 截断 JSON 字段提取
    """
    import re

    # Tier 1: direct parse
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass

    # Tier 2: markdown fence
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Tier 3: any JSON object
    match = re.search(r"\{[^{}]*\}", raw)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Tier 4: truncated JSON — extract key fields
    result = {}
    for key in ("split", "reasoning"):
        match = re.search(rf'"{key}"\s*:\s*(true|false|"[^"]*")', raw)
        if match:
            val = match.group(1)
            if val == "true":
                result[key] = True
            elif val == "false":
                result[key] = False
            else:
                result[key] = val.strip('"')

    return result if "split" in result else {"split": False}
