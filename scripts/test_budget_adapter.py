#!/usr/bin/env python3
"""budget_adapter 冒烟测试 — 不调用 API，仅验证导入与返回值范围。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from budget_adapter import get_budget_ratio  # noqa: E402


async def main() -> int:
    ratio = await get_budget_ratio()
    ok = 0.0 <= ratio <= 1.0
    print(f"budget_ratio={ratio:.4f}")
    print(f"Result: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
