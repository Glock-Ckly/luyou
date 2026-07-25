from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from model_router.domain.execution_task import ExecutionTask, TaskConflict


class SQLiteTaskRepository:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_tasks (
                    task_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    technology_stack TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    acceptance_criteria TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def add(self, task: ExecutionTask) -> None:
        values = self._to_row(task)
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        with self._connection() as connection:
            try:
                connection.execute(
                    f"INSERT INTO execution_tasks ({columns}) VALUES ({placeholders})",
                    tuple(values.values()),
                )
            except sqlite3.IntegrityError as error:
                raise TaskConflict("task already exists") from error

    def get(self, task_id: str) -> ExecutionTask | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM execution_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
        return self._from_row(row) if row else None

    def list(
        self, *, status: str | None = None, task_type: str | None = None, search: str | None = None
    ) -> list[ExecutionTask]:
        clauses: list[str] = []
        parameters: list[str] = []
        if status:
            clauses.append("status = ?")
            parameters.append(status)
        if task_type:
            clauses.append("task_type = ?")
            parameters.append(task_type)
        if search:
            clauses.append("(LOWER(title) LIKE ? OR LOWER(description) LIKE ? OR LOWER(tags) LIKE ?)")
            pattern = f"%{search.strip().lower()}%"
            parameters.extend((pattern, pattern, pattern))
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM execution_tasks{where} ORDER BY updated_at DESC, task_id ASC",
                parameters,
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def update(self, task: ExecutionTask, *, expected_version: int) -> None:
        values = self._to_row(task)
        assignments = ", ".join(f"{column} = ?" for column in values if column != "task_id")
        parameters = [values[column] for column in values if column != "task_id"]
        parameters.extend((task.task_id, expected_version))
        with self._connection() as connection:
            cursor = connection.execute(
                f"UPDATE execution_tasks SET {assignments} WHERE task_id = ? AND version = ?",
                parameters,
            )
            if cursor.rowcount != 1:
                raise TaskConflict("task version conflict")

    def delete(self, task_id: str) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM execution_tasks WHERE task_id = ?", (task_id,))

    @staticmethod
    def _to_row(task: ExecutionTask) -> dict:
        values = task.to_dict()
        for field in ("technology_stack", "acceptance_criteria", "tags"):
            values[field] = json.dumps(values[field], ensure_ascii=False)
        return values

    @staticmethod
    def _from_row(row: sqlite3.Row) -> ExecutionTask:
        values = dict(row)
        for field in ("technology_stack", "acceptance_criteria", "tags"):
            values[field] = json.loads(values[field])
        return ExecutionTask.from_dict(values)
