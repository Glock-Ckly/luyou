#!/usr/bin/env python3
"""L2 分类器评估 — 对标注样本跑 L2，输出准确率报告。

通过标准: routing accuracy >= 75%，且 implementation/debugging 路由零失误。
（architecture 与 system_design 路由到同一模型时视为等价。）
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from l2_classifier import classify_l2  # noqa: E402
from routing_table import TASK_TO_MODEL  # noqa: E402

SAMPLES_PATH = ROOT / "config" / "l2_eval_samples.json"
STRICT_CRITICAL = {"debugging", "implementation"}
MIN_ACCURACY = 0.75


def routing_match(expected: str, got: str) -> bool:
    if expected == got:
        return True
    exp_model = TASK_TO_MODEL.get(expected)
    got_model = TASK_TO_MODEL.get(got)
    return bool(exp_model and got_model and exp_model == got_model)


async def main() -> int:
    samples = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))
    print(f"=== L2 Eval: {len(samples)} samples ===\n")

    correct = 0
    strict_correct = 0
    failures: list[str] = []
    strict_failures: list[str] = []
    confusion: Counter[tuple[str, str]] = Counter()

    for i, sample in enumerate(samples, 1):
        sid = sample["id"]
        prompt = sample["prompt"]
        expected = sample["expected"]
        result = await classify_l2(prompt)
        got = result["task_type"]

        r_ok = routing_match(expected, got)
        s_ok = got == expected
        if r_ok:
            correct += 1
        else:
            failures.append(f"  {sid}: expected={expected}, got={got} | {prompt[:60]}...")
        if s_ok:
            strict_correct += 1
        elif not r_ok:
            strict_failures.append(f"  {sid}: expected={expected}, got={got}")
        confusion[(expected, got)] += 1

        mark = "OK" if r_ok else "FAIL"
        tag = "" if s_ok else (" ~" if r_ok else "")
        print(f"[{i:02d}/{len(samples)}] {mark}{tag} {sid}: {got} (exp {expected})")

    accuracy = correct / len(samples)
    strict_acc = strict_correct / len(samples)
    critical_bad = [f for f in failures if any(f"expected={t}" in f for t in STRICT_CRITICAL)]

    print(f"\n=== Summary ===")
    print(f"Routing accuracy: {correct}/{len(samples)} = {accuracy:.1%}")
    print(f"Strict label accuracy: {strict_correct}/{len(samples)} = {strict_acc:.1%}")
    print(f"Threshold (routing): {MIN_ACCURACY:.0%}")

    if failures:
        print(f"\nRouting failures ({len(failures)}):")
        print("\n".join(failures))

    print("\nTop confusion pairs (expected → got):")
    for (exp, got), cnt in confusion.most_common(8):
        if exp != got:
            print(f"  {exp} → {got}: {cnt}")

    passed = accuracy >= MIN_ACCURACY and len(critical_bad) == 0
    print(f"\nResult: {'PASS' if passed else 'FAIL'}")
    if critical_bad:
        print(f"Critical routing failures (impl/debug): {len(critical_bad)}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
