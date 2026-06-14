"""
L2 LLM 分类器 — DeepSeek 精确分类层

当 L1 关键词快筛置信度不足时，由本模块调用 LLM 做 task_type 判定。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from relay_config import apply_relay_env, resolve_model

apply_relay_env()

_L2_PROMPT_PATH = Path(__file__).parent / "prompts" / "classifier_v3.txt"
DEFAULT_L2_MODEL = "deepseek/deepseek-chat"


def get_l2_system_prompt() -> str:
    return _L2_PROMPT_PATH.read_text(encoding="utf-8").strip()


def parse_l2_json(raw: str) -> dict:
    """4-tier JSON 解析（与 orchestrator 保持一致）。"""
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

    result: dict = {}
    for key in ("task_type", "complexity", "confidence", "reasoning"):
        m = re.search(rf'"{key}"\s*:\s*"([^"]*)"', raw)
        if m:
            result[key] = m.group(1)
        else:
            m = re.search(rf'"{key}"\s*:\s*([\d.]+)', raw)
            if m:
                result[key] = float(m.group(1))
    return result if "task_type" in result else {"task_type": "uncertain"}


async def classify_l2(
    prompt: str,
    *,
    l2_model: str = DEFAULT_L2_MODEL,
    system_prompt: str | None = None,
) -> dict:
    """调用 L2 LLM 分类器，返回标准分类 dict。"""
    from relay_llm import call_llm

    system = system_prompt or get_l2_system_prompt()
    try:
        resp = await call_llm(
            model=resolve_model(l2_model),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=256,
        )
        data = parse_l2_json(resp.content)
        return {
            "task_type": data.get("task_type", "uncertain"),
            "complexity": {"simple": 1, "moderate": 3, "complex": 5, "deep_reasoning": 5}
                .get(str(data.get("complexity", "moderate")), 3),
            "confidence": min(1.0, max(0.0, float(data.get("confidence", 0.5)))),
            "reasoning": data.get("reasoning", ""),
            "source": "L2",
            "l2_model": l2_model,
            "l2_cost_usd": resp.cost_usd,
        }
    except Exception as exc:
        return {
            "task_type": "uncertain",
            "complexity": 3,
            "confidence": 0.0,
            "reasoning": f"L2 classification failed: {exc}",
            "source": "fallback",
            "l2_model": l2_model,
            "l2_cost_usd": 0.0,
        }
