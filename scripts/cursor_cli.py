#!/usr/bin/env python3
"""Cursor Queue 独立 CLI — 不依赖 llm-router 打包。

用法:
  python scripts/cursor_cli.py list [pending|all|done]
  python scripts/cursor_cli.py pop
  python scripts/cursor_cli.py done <task_id>
  python scripts/cursor_cli.py push <type> "<instruction>" [file] [context]
  python scripts/cursor_cli.py stats

也可通过入口点: python -m scripts.cursor_cli (若从项目根运行)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from cursor_queue import push, pop, mark_done, list_tasks, stats  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    cmd = sys.argv[1]

    if cmd == "list":
        status = sys.argv[2] if len(sys.argv) > 2 else "pending"
        tasks = list_tasks(status)
        if not tasks:
            print(f"No tasks ({status}).")
            return 0
        for t in tasks:
            print(f"[{t['status']}] {t['id']}")
            print(f"  type: {t['type']}")
            if t.get("file"):
                print(f"  file: {t['file']}")
            print(f"  instruction: {t['instruction'][:120]}")
        return 0

    if cmd == "pop":
        t = pop()
        if not t:
            print("Queue is empty.")
            return 0
        print(f"ID: {t.id}")
        print(f"Type: {t.type}")
        print(f"File: {t.file or '(none)'}")
        print(f"Instruction: {t.instruction}")
        if t.context:
            print(f"Context: {t.context}")
        return 0

    if cmd == "done":
        if len(sys.argv) < 3:
            print("Usage: cursor_cli.py done <task_id>")
            return 1
        ok = mark_done(sys.argv[2])
        print("Marked done." if ok else f"Task {sys.argv[2]} not found.")
        return 0 if ok else 1

    if cmd == "push":
        if len(sys.argv) < 4:
            print('Usage: cursor_cli.py push <type> "<instruction>" [file] [context]')
            return 1
        t = push(
            task_type=sys.argv[2],
            instruction=sys.argv[3],
            file=sys.argv[4] if len(sys.argv) > 4 else None,
            context=sys.argv[5] if len(sys.argv) > 5 else "",
        )
        print(f"Pushed: {t.id}")
        return 0

    if cmd == "stats":
        s = stats()
        print(f"Total: {s['total']}, Pending: {s['pending']}, Done: {s['done']}")
        return 0

    print(f"Unknown command: {cmd}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
