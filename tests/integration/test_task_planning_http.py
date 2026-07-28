from __future__ import annotations

import http.client
import importlib.util
import json
import os
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "dashboard_planning_server_under_test", ROOT / "scripts" / "dashboard_server.py"
)
dashboard_server = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(dashboard_server)


class FakePlanningService:
    async def analyze(self, payload):
        return {"analysis_id": "analysis_123", "task": {"scope": ""}, "checklist_markdown": "# Plan"}

    def create_from_analysis(self, payload):
        return {"task_id": "task_planned", "title": "Planned", "plan_url": "/api/tasks/task_planned/plan.md"}

    def read_plan(self, task_id):
        if task_id == "task_missing":
            from model_router.domain.task_analysis import TaskPlanNotFound
            raise TaskPlanNotFound(task_id)
        return "# Plan\n"


class TaskPlanningHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_token = os.environ.get("MODEL_ROUTER_API_TOKEN")
        os.environ["MODEL_ROUTER_API_TOKEN"] = "planning-secret"
        dashboard_server._TASK_PLANNING_SERVICE = FakePlanningService()
        cls.server = dashboard_server.ThreadingHTTPServer(("127.0.0.1", 0), dashboard_server.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        dashboard_server._TASK_PLANNING_SERVICE = None
        if cls.original_token is None:
            os.environ.pop("MODEL_ROUTER_API_TOKEN", None)
        else:
            os.environ["MODEL_ROUTER_API_TOKEN"] = cls.original_token

    def request(self, method, path, body=None, token="planning-secret"):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        encoded = json.dumps(body).encode("utf-8") if body is not None else None
        connection.request(method, path, body=encoded, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        content_type = response.getheader("Content-Type", "")
        payload = json.loads(raw.decode("utf-8")) if "json" in content_type and raw else raw.decode("utf-8")
        connection.close()
        return response.status, content_type, payload

    def test_analyze_requires_authentication(self):
        status, _, payload = self.request("POST", "/api/tasks/analyze", {"goal": "Build a service"}, token="")
        self.assertEqual(401, status)
        self.assertEqual("invalid_api_key", payload["error"]["code"])

    def test_analyze_accepts_goal_with_optional_scope(self):
        status, _, payload = self.request("POST", "/api/tasks/analyze", {"goal": "Build a service"})
        self.assertEqual(200, status)
        self.assertEqual("", payload["task"]["scope"])

    def test_create_from_analysis_returns_plan_url(self):
        status, _, payload = self.request("POST", "/api/tasks/from-analysis", {"analysis": {}})
        self.assertEqual(201, status)
        self.assertEqual("/api/tasks/task_planned/plan.md", payload["plan_url"])

    def test_plan_markdown_uses_markdown_content_type(self):
        status, content_type, payload = self.request("GET", "/api/tasks/task_planned/plan.md")
        self.assertEqual(200, status)
        self.assertIn("text/markdown", content_type)
        self.assertEqual("# Plan\n", payload)


if __name__ == "__main__":
    unittest.main()
