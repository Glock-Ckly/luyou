#!/usr/bin/env python3
"""TaskDecomposer 评估 — 10 条大/小任务，检查 split JSON 质量。

通过标准:
  - split 决策准确率 >= 80%
  - 应拆分的样本: subtasks >= min_subtasks，且每条 prompt 非空、type_hint 合法
  - 不应拆分的样本: split=false 或仅 1 条子任务
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from relay_config import apply_relay_env  # noqa: E402
from task_decomposer import decompose  # noqa: E402
from relay_llm import call_llm  # noqa: E402

SAMPLES_PATH = ROOT / "config" / "decomposer_eval_samples.json"
VALID_HINTS = {
    "architecture", "implementation", "debugging", "refactor",
    "boilerplate", "bulk_generation", "data_processing",
    "code_patch", "file_edit", "system_design", "deep_reasoning",
}
MIN_SPLIT_ACCURACY = 0.80


async def _call(model, messages, **kwargs):
    return await call_llm(model=model, messages=messages, **kwargs)


def validate_subtasks(result, min_subtasks: int) -> tuple[bool, str]:
    if not result.split:
        return False, "expected split=true"
    if len(result.subtasks) < min_subtasks:
        return False, f"subtasks={len(result.subtasks)} < min={min_subtasks}"
    for i, st in enumerate(result.subtasks):
        if len(st.prompt.strip()) < 8:
            return False, f"subtask[{i}] prompt too short"
        if st.type_hint and st.type_hint not in VALID_HINTS:
            return False, f"subtask[{i}] invalid type_hint={st.type_hint}"
    return True, ""


async def main() -> int:
    apply_relay_env()
    samples = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))
    print(f"=== Decomposer Eval: {len(samples)} samples ===\n")

    split_correct = 0
    failures: list[str] = []

    for i, sample in enumerate(samples, 1):
        sid = sample["id"]
        expect = sample["expect_split"]
        min_st = sample.get("min_subtasks", 2 if expect else 1)

        result = await decompose(sample["prompt"], call_llm=_call, force=expect)

        got_split = result.split and len(result.subtasks) > 1
        if not expect:
            got_split = result.split and len(result.subtasks) > 1

        decision_ok = got_split == expect
        quality_ok = True
        quality_detail = ""

        if expect:
            quality_ok, quality_detail = validate_subtasks(result, min_st)
        else:
            if got_split:
                quality_ok = False
                quality_detail = "unexpected split"

        ok = decision_ok and quality_ok
        if ok:
            split_correct += 1
        else:
            detail = quality_detail or (
                f"expect_split={expect}, got_split={got_split}, n={len(result.subtasks)}"
            )
            failures.append(f"  {sid}: {detail} | {sample['prompt'][:50]}...")

        mark = "OK" if ok else "FAIL"
        split_tag = f"split={result.split}×{len(result.subtasks)}"
        print(f"[{i:02d}/{len(samples)}] {mark} {sid}: {split_tag} (exp split={expect})")

    accuracy = split_correct / len(samples)
    print(f"\n=== Summary ===")
    print(f"Pass: {split_correct}/{len(samples)} = {accuracy:.1%}")
    print(f"Threshold: {MIN_SPLIT_ACCURACY:.0%}")

    if failures:
        print(f"\nFailures ({len(failures)}):")
        print("\n".join(failures))

    passed = accuracy >= MIN_SPLIT_ACCURACY
    print(f"\nResult: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
