# Cursor 队列（已完成）

## 原因

Cursor Composer **无公开 API**。`code_patch` / `file_edit` 路由到本地 JSON 队列，由用户手动粘贴到 Cursor 执行。

## 存储

`~/.llm-router/cursor_queue.json`

```json
{
  "tasks": [{
    "id": "cur_20260614_130738_79e149",
    "type": "code_patch",
    "file": null,
    "instruction": "...",
    "context": "",
    "status": "pending",
    "created": "..."
  }],
  "stats": { "total": 1, "pending": 1, "done": 0 }
}
```

## API

文件：`src/cursor_queue.py`

- `push(task_type, instruction, file?, context?)` → `CursorTask`
- `pop()` → 最早 pending，标为 in_progress
- `mark_done(task_id)`
- `list_tasks(status)` / `stats()`

## CLI

文件：`scripts/cursor_cli.py`

```bash
python scripts/cursor_cli.py list [pending|all|done]
python scripts/cursor_cli.py pop
python scripts/cursor_cli.py push code_patch "修改 auth.py 过期时间"
python scripts/cursor_cli.py done <task_id>
python scripts/cursor_cli.py stats
```

冒烟：`scripts/test_cursor_cli.py` — PASS

## 工作流

1. orchestrator 判为 `code_patch` → `push`
2. 返回：`Task queued. Run cursor-pop to retrieve (id: ...)`
3. 用户 `cursor_cli.py pop` → 复制到 Cursor Composer
4. 完成后 `cursor_cli.py done <id>`
