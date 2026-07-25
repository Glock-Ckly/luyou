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


if __name__ == "__main__":
    unittest.main()
