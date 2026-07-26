from __future__ import annotations

import http.client
import importlib.util
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "dashboard_task_server_under_test", ROOT / "scripts" / "dashboard_server.py"
)
dashboard_server = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(dashboard_server)


class TaskCrudHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.original_db = os.environ.get("MODEL_ROUTER_DB_PATH")
        cls.original_token = os.environ.get("MODEL_ROUTER_API_TOKEN")
        os.environ["MODEL_ROUTER_DB_PATH"] = str(Path(cls.temp.name) / "tasks.db")
        os.environ["MODEL_ROUTER_API_TOKEN"] = "task-secret"
        dashboard_server._TASK_SERVICE = None
        cls.server = dashboard_server.ThreadingHTTPServer(("127.0.0.1", 0), dashboard_server.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.temp.cleanup()
        dashboard_server._TASK_SERVICE = None
        for name, value in (
            ("MODEL_ROUTER_DB_PATH", cls.original_db),
            ("MODEL_ROUTER_API_TOKEN", cls.original_token),
        ):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def request(self, method, path, body=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        encoded = json.dumps(body).encode("utf-8") if body is not None else None
        connection.request(
            method,
            path,
            body=encoded,
            headers={"Authorization": "Bearer task-secret", "Content-Type": "application/json"},
        )
        response = connection.getresponse()
        raw = response.read()
        payload = json.loads(raw.decode("utf-8")) if raw else None
        connection.close()
        return response.status, payload

    def create_task(self, **overrides):
        payload = {
            "title": "Phase 15 task",
            "description": "Exercise the task contract",
            "task_type": "implementation",
        }
        payload.update(overrides)
        status, created = self.request("POST", "/api/tasks", payload)
        self.assertEqual(201, status)
        return created

    def test_full_crud_contract(self):
        status, created = self.request(
            "POST",
            "/api/tasks",
            {"title": "Nested workbench", "description": "Build CRUD UI", "task_type": "implementation", "priority": "high", "tags": ["ui"]},
        )
        self.assertEqual(201, status)
        task_id = created["task_id"]

        status, listing = self.request("GET", "/api/tasks?search=workbench")
        self.assertEqual(200, status)
        self.assertEqual(1, listing["total"])

        status, detail = self.request("GET", f"/api/tasks/{task_id}")
        self.assertEqual(200, status)
        self.assertEqual("Nested workbench", detail["title"])

        status, updated = self.request(
            "PUT",
            f"/api/tasks/{task_id}",
            {**detail, "title": "Updated workbench", "status": "ready"},
        )
        self.assertEqual(200, status)
        self.assertEqual(2, updated["version"])

        status, _ = self.request("DELETE", f"/api/tasks/{task_id}")
        self.assertEqual(204, status)

        status, missing = self.request("GET", f"/api/tasks/{task_id}")
        self.assertEqual(404, status)
        self.assertEqual("task_not_found", missing["error"]["code"])

    def test_update_rejects_non_numeric_version(self):
        task = self.create_task()
        status, payload = self.request(
            "PUT", f"/api/tasks/{task['task_id']}", {"version": "abc"}
        )
        self.assertEqual(400, status)
        self.assertEqual("invalid_task", payload["error"]["code"])

    def test_update_rejects_fractional_version(self):
        task = self.create_task()
        status, payload = self.request(
            "PUT", f"/api/tasks/{task['task_id']}", {"version": 1.5}
        )
        self.assertEqual(400, status)
        self.assertEqual("invalid_task", payload["error"]["code"])

    def test_create_rejects_string_tags(self):
        status, payload = self.request(
            "POST",
            "/api/tasks",
            {
                "title": "Invalid tags",
                "description": "Tags must be an array",
                "task_type": "implementation",
                "tags": "ab",
            },
        )
        self.assertEqual(400, status)
        self.assertEqual("invalid_task", payload["error"]["code"])

    def test_create_rejects_string_technology_stack(self):
        status, payload = self.request(
            "POST",
            "/api/tasks",
            {
                "title": "Invalid stack",
                "description": "Technology stack must be an array",
                "task_type": "implementation",
                "technology_stack": "python",
            },
        )
        self.assertEqual(400, status)
        self.assertEqual("invalid_task", payload["error"]["code"])

    def test_create_rejects_mapping_acceptance_criteria(self):
        status, payload = self.request(
            "POST",
            "/api/tasks",
            {
                "title": "Invalid criteria",
                "description": "Acceptance criteria must be an array",
                "task_type": "implementation",
                "acceptance_criteria": {"a": 1},
            },
        )
        self.assertEqual(400, status)
        self.assertEqual("invalid_task", payload["error"]["code"])

    def test_delete_running_task_returns_conflict_and_preserves_row(self):
        task = self.create_task(status="running")
        task_id = task["task_id"]

        status, payload = self.request("DELETE", f"/api/tasks/{task_id}")
        self.assertEqual(409, status)
        self.assertEqual("task_conflict", payload["error"]["code"])

        status, persisted = self.request("GET", f"/api/tasks/{task_id}")
        self.assertEqual(200, status)
        self.assertEqual("running", persisted["status"])

    def test_delete_unknown_task_returns_not_found(self):
        status, payload = self.request("DELETE", "/api/tasks/task_missing_phase_15")
        self.assertEqual(404, status)
        self.assertEqual("task_not_found", payload["error"]["code"])


if __name__ == "__main__":
    unittest.main()
