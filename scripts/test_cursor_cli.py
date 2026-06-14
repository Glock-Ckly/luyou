#!/usr/bin/env python3
"""cursor_cli 冒烟测试 — 不依赖 API。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "cursor_cli.py"


def main() -> int:
    proc = subprocess.run(
        [sys.executable, str(CLI), "stats"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    print(proc.stdout or proc.stderr)
    ok = proc.returncode == 0 and "Total:" in (proc.stdout or "")
    print(f"Result: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
