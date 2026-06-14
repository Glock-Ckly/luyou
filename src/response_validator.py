"""
Response Validator — 轻量后验校验

对模型返回结果做结构性检查。不做内容正确性判定 (太贵/不可靠)。

校验 3 层:
  L1 语法层: 代码块完整? JSON 合法?
  L2 结构层: 包含要求的所有部分? 输出不截断?
  L3 标记层: 是否含 "I cannot"/"as an AI"/"抱歉"?

不合格动作:
  L1 失败 → 同模型重试 (最多 1 次)
  L2 失败 → 升级模型重试
  L3 失败 → 升级模型重试
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum


class ValidationStatus(Enum):
    PASS = "pass"
    RETRY_SAME = "retry_same"       # L1 失败 → 同模型重试
    RETRY_UPGRADE = "retry_upgrade"  # L2/L3 失败 → 升级模型


@dataclass
class ValidationResult:
    status: ValidationStatus
    failures: list[str] = field(default_factory=list)
    reasoning: str = ""


# ── 标记模式 (L3) ────────────────────────────────────
_REFUSAL_PATTERNS = [
    r"(?i)i\s+(cannot|can't)\s+(fulfill|complete|do|help|assist|comply)",
    r"(?i)as\s+an\s+AI\s+(language\s+model|assistant)",
    r"(?i)i\s+apologize.*\b(but|however)\b",
    r"抱歉.{0,20}(无法|不能|没办法)",
    r"(?i)(i\s+don'?t\s+have|i\s+lack)\s+(the\s+)?(ability|capability|context)",
    r"(?i)it\s+would\s+not\s+be\s+(appropriate|ethical|responsible)",
]


def validate(response_text: str, expected_type: str = "code") -> ValidationResult:
    """校验模型响应。

    Args:
        response_text: 模型返回的完整文本
        expected_type: 期望的响应类型 (code/analysis/text)

    Returns:
        ValidationResult
    """
    failures = []

    # ── L1 语法层 ──────────────────────────────────
    if expected_type == "code" or "```" in response_text:
        l1_failures = _check_code_blocks(response_text)
        failures.extend(l1_failures)

    # 检查 JSON (如果有)
    l1_json = _check_json_blocks(response_text)
    failures.extend(l1_json)

    # ── L2 结构层 ──────────────────────────────────
    l2_failures = _check_truncation(response_text)
    failures.extend(l2_failures)

    # ── L3 标记层 ──────────────────────────────────
    l3_failures = _check_refusal(response_text)
    failures.extend(l3_failures)

    if not failures:
        return ValidationResult(status=ValidationStatus.PASS)

    # 判定动作
    # L1 失败 → 同模型重试
    if any("L1" in f for f in failures):
        return ValidationResult(
            status=ValidationStatus.RETRY_SAME,
            failures=failures,
            reasoning=f"L1 syntax failures: {failures}",
        )

    # L2/L3 → 升级
    return ValidationResult(
        status=ValidationStatus.RETRY_UPGRADE,
        failures=failures,
        reasoning=f"L2/L3 failures: {failures}",
    )


def _check_code_blocks(text: str) -> list[str]:
    """检查代码块是否完整 (开闭配对)"""
    failures = []
    opens = len(re.findall(r"```\w*", text))
    # 除去 closing ``` 后应该是偶数
    if opens % 2 != 0:
        failures.append("L1: unmatched code fence — output truncated mid-block")
    # 检查是否有开无闭 (常见于截断)
    if "```" in text and text.rstrip().endswith("```"):
        pass  # 正常闭合
    elif "```" in text and not text.rstrip().endswith("```"):
        # 最后一个 ``` 后面没有闭合
        last_fence = text.rfind("```")
        if last_fence > 0 and text[last_fence:].count("```") % 2 != 0:
            failures.append("L1: code block opened but not closed — likely truncated")
    return failures


def _check_json_blocks(text: str) -> list[str]:
    """检查 JSON 块是否合法"""
    failures = []
    # 找所有可能的 JSON 块
    for match in re.finditer(r"\{[^{}]*\}", text):
        try:
            json.loads(match.group(0))
        except json.JSONDecodeError:
            pass  # 有些 { } 不是 JSON
    # 找明确标注的 JSON
    for match in re.finditer(r"```json\s*([\s\S]*?)```", text):
        try:
            json.loads(match.group(1))
        except json.JSONDecodeError:
            failures.append("L1: invalid JSON in marked code block")
    return failures


def _check_truncation(text: str) -> list[str]:
    """检查输出是否截断"""
    failures = []
    # 以明显的半截标记结尾
    truncation_markers = [
        r"\.\.\.$",           # 以省略号结尾
        r"[a-z_]+\($",        # 函数调用被截断
        r"[^;]\s*$",          # Python 语句未完成? (弱信号)
    ]
    # 更可靠的截断信号: 不完整的以上下文
    if text.rstrip().endswith("...") and len(text.rstrip()) < 100:
        failures.append("L2: response appears truncated (ends with ...)")
    # 代码块未闭合已在 L1 检测，此处补充自然语言截断
    if re.search(r"(?i)(continuing|to\s+be\s+continued|\.\.\.\s*$)", text[-50:]):
        failures.append("L2: response explicitly marked as incomplete")
    return failures


def _check_refusal(text: str) -> list[str]:
    """检查是否包含拒绝/道歉标记"""
    failures = []
    for pattern in _REFUSAL_PATTERNS:
        if re.search(pattern, text):
            failures.append(f"L3: refusal/apology pattern detected: {pattern[:40]}...")
            break  # 一个就够了
    return failures


# ── 自测 ─────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        # (response, expected_status)
        ("def foo():\n    return 42\n", ValidationStatus.PASS),
        ("def foo():\n    return 42\n    ```", ValidationStatus.RETRY_SAME),
        ("I cannot fulfill this request as it involves...", ValidationStatus.RETRY_UPGRADE),
        ("Here is the code:\n```python\ndef foo():\n    return 42\n```", ValidationStatus.PASS),
    ]

    for resp, expected in tests:
        result = validate(resp)
        ok = result.status == expected
        print(f"{'OK' if ok else 'FAIL'} [{result.status.value}] {resp[:50]}...")
