#!/usr/bin/env python3
"""安装 Cursor MCP — 调用 llm-router install --host cursor。

用法:
  python scripts/install_cursor_mcp.py --dry-run   # 仅预览
  python scripts/install_cursor_mcp.py --apply      # 写入 ~/.cursor/mcp.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CURSOR_MCP = Path.home() / ".cursor" / "mcp.json"
SNIPPET = ROOT / "config" / "cursor_mcp_snippet.json"


def _read_mcp(path: Path) -> dict:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def preview() -> None:
    current = _read_mcp(CURSOR_MCP)
    snippet = _read_mcp(SNIPPET)
    has = "llm-router" in current.get("mcpServers", {})
    print(f"Target: {CURSOR_MCP}")
    print(f"llm-router already registered: {has}")
    print(f"Snippet command: {snippet.get('mcpServers', {}).get('llm-router', {})}")
    print("\nWill run: llm-router install --host cursor")
    print("(writes ~/.cursor/mcp.json + ~/.cursor/rules/llm-router.md)")


def apply() -> int:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        ["llm-router", "install", "--host", "cursor"],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    if proc.returncode != 0:
        print(f"FAIL: exit {proc.returncode}")
        return proc.returncode

    if not CURSOR_MCP.is_file():
        print(f"FAIL: {CURSOR_MCP} not created")
        return 1
    cfg = _read_mcp(CURSOR_MCP)
    if "llm-router" not in cfg.get("mcpServers", {}):
        print("FAIL: llm-router not in mcpServers")
        return 1
    print(f"PASS: llm-router registered in {CURSOR_MCP}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--apply", action="store_true", help="Run install")
    args = parser.parse_args()

    if args.apply:
        return apply()
    preview()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
