"""
Cursor Queue — 手动交付容器

因为 Cursor Composer 没有公开 API，路由到 Cursor 的任务推入本地 JSON 队列，
用户手动取出喂给 Cursor，完成后标记 done。

存储: ~/.llm-router/cursor_queue.json

CLI:
  llm-router cursor-list    查看队列
  llm-router cursor-pop     弹出一个待处理任务
  llm-router cursor-done ID 标记完成
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _queue_path() -> Path:
    """获取队列文件路径"""
    base = Path(os.environ.get("LLM_ROUTER_HOME", Path.home() / ".llm-router"))
    base.mkdir(parents=True, exist_ok=True)
    return base / "cursor_queue.json"


def _load_queue() -> dict:
    """加载队列"""
    path = _queue_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"tasks": [], "stats": {"total": 0, "pending": 0, "done": 0}}


def _save_queue(data: dict) -> None:
    """保存队列"""
    path = _queue_path()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@dataclass
class CursorTask:
    """一个 Cursor 任务"""
    id: str
    type: str  # code_patch | file_edit
    file: str | None
    instruction: str
    context: str = ""
    suggested_diff: str | None = None
    status: str = "pending"
    created: str = ""
    done: str | None = None


def push(
    task_type: str,
    instruction: str,
    file: str | None = None,
    context: str = "",
) -> CursorTask:
    """推入一个任务到队列。

    Args:
        task_type: code_patch | file_edit
        instruction: 修改说明
        file: 目标文件路径
        context: 上下文信息

    Returns:
        CursorTask
    """
    queue = _load_queue()

    task_id = f"cur_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    task = CursorTask(
        id=task_id,
        type=task_type,
        file=file,
        instruction=instruction,
        context=context,
        status="pending",
        created=datetime.now(timezone.utc).isoformat(),
    )

    queue["tasks"].append({
        "id": task.id,
        "type": task.type,
        "file": task.file,
        "instruction": task.instruction,
        "context": task.context,
        "suggested_diff": task.suggested_diff,
        "status": task.status,
        "created": task.created,
        "done": task.done,
    })

    # 更新统计
    queue["stats"]["total"] = len(queue["tasks"])
    queue["stats"]["pending"] = sum(1 for t in queue["tasks"] if t["status"] == "pending")
    queue["stats"]["done"] = sum(1 for t in queue["tasks"] if t["status"] == "done")

    _save_queue(queue)
    return task


def pop() -> CursorTask | None:
    """弹出最早的待处理任务 (不删除，标记为 in_progress)"""
    queue = _load_queue()

    pending = [t for t in queue["tasks"] if t["status"] == "pending"]
    if not pending:
        return None

    task_data = pending[0]
    task_data["status"] = "in_progress"
    _save_queue(queue)

    return CursorTask(**task_data)


def mark_done(task_id: str) -> bool:
    """标记任务完成"""
    queue = _load_queue()

    for t in queue["tasks"]:
        if t["id"] == task_id:
            t["status"] = "done"
            t["done"] = datetime.now(timezone.utc).isoformat()
            queue["stats"]["pending"] = sum(
                1 for x in queue["tasks"] if x["status"] == "pending"
            )
            queue["stats"]["done"] = sum(
                1 for x in queue["tasks"] if x["status"] == "done"
            )
            _save_queue(queue)
            return True

    return False


def list_tasks(status: str = "pending") -> list[dict]:
    """列出指定状态的任务"""
    queue = _load_queue()
    if status == "all":
        return queue["tasks"]
    return [t for t in queue["tasks"] if t["status"] == status]


def stats() -> dict:
    """获取统计"""
    return _load_queue()["stats"]


# ── CLI ─────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: cursor_queue.py <push|pop|done|list|stats> [args]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "push":
        # cursor_queue.py push code_patch "fix token bug" "src/auth.py" "JWT refresh"
        t = push(
            task_type=sys.argv[2] if len(sys.argv) > 2 else "code_patch",
            instruction=sys.argv[3] if len(sys.argv) > 3 else "no instruction",
            file=sys.argv[4] if len(sys.argv) > 4 else None,
            context=sys.argv[5] if len(sys.argv) > 5 else "",
        )
        print(f"Pushed: {t.id}")

    elif cmd == "pop":
        t = pop()
        if t:
            print(f"ID: {t.id}")
            print(f"Type: {t.type}")
            print(f"File: {t.file}")
            print(f"Instruction: {t.instruction}")
            print(f"Context: {t.context}")
        else:
            print("Queue is empty.")

    elif cmd == "done":
        task_id = sys.argv[2] if len(sys.argv) > 2 else ""
        ok = mark_done(task_id)
        print("Marked done." if ok else f"Task {task_id} not found.")

    elif cmd == "list":
        s = sys.argv[2] if len(sys.argv) > 2 else "pending"
        tasks = list_tasks(s)
        for t in tasks:
            print(f"[{t['status']}] {t['id']}: {t['instruction'][:60]}")

    elif cmd == "stats":
        s = stats()
        print(f"Total: {s['total']}, Pending: {s['pending']}, Done: {s['done']}")

    else:
        print(f"Unknown command: {cmd}")
