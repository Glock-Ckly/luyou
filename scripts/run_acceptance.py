#!/usr/bin/env python3
"""一键验收 — smoke + 全部 eval。任一步失败即非零退出。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = [
    "smoke_relay.py",
    "eval_l2.py",
    "eval_decomposer.py",
    "eval_e2e.py",
    "test_budget_adapter.py",
    "test_cursor_cli.py",
    "test_dashboard_demo.py",
]


def main() -> int:
    failed = 0
    for name in SCRIPTS:
        print(f"\n{'='*50}\n>>> {name}\n{'='*50}")
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / name)],
            cwd=str(ROOT),
            env=env,
        )
        if proc.returncode != 0:
            print(f"FAILED: {name} (exit {proc.returncode})")
            failed += 1
        else:
            print(f"OK: {name}")

    print(f"\n=== Acceptance: {len(SCRIPTS) - failed}/{len(SCRIPTS)} passed ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
