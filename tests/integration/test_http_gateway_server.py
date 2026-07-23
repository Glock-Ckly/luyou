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
    "dashboard_server_under_test", ROOT / "scripts" / "dashboard_server.py"
)
dashboard_server = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(dashboard_server)


class HttpGatewayServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_token = os.environ.get("MODEL_ROUTER_API_TOKEN")
        cls.original_origins = os.environ.get("MODEL_ROUTER_ALLOWED_ORIGINS")
        os.environ["MODEL_ROUTER_API_TOKEN"] = "contract-secret"
        os.environ["MODEL_ROUTER_ALLOWED_ORIGINS"] = "http://allowed.example"
        cls.original_dispatch = dashboard_server._run_dispatch
        dashboard_server._run_dispatch = lambda prompt, workdir: {
            "trace_id": "tr_http",
            "selected_model": "deepseek/deepseek-v4-pro",
            "result": f"routed: {prompt}",
        }
        cls.server = dashboard_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), dashboard_server.Handler
        )
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        dashboard_server._run_dispatch = cls.original_dispatch
        for name, value in (
            ("MODEL_ROUTER_API_TOKEN", cls.original_token),
            ("MODEL_ROUTER_ALLOWED_ORIGINS", cls.original_origins),
        ):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        encoded = json.dumps(body).encode("utf-8") if body is not None else None
        request_headers = {"Content-Type": "application/json", **(headers or {})}
        connection.request(method, path, body=encoded, headers=request_headers)
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        response_headers = dict(response.getheaders())
        connection.close()
        return response.status, payload, response_headers

    def test_health_is_public(self):
        status, payload, _ = self.request("GET", "/health")
        self.assertEqual(200, status)
        self.assertEqual("ok", payload["status"])

    def test_api_requires_token_and_does_not_reflect_unknown_origin(self):
        status, payload, headers = self.request(
            "GET", "/api/catalog", headers={"Origin": "http://evil.example"}
        )
        self.assertEqual(401, status)
        self.assertEqual("invalid_api_key", payload["error"]["code"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_openai_chat_completion_contract(self):
        status, payload, headers = self.request(
            "POST",
            "/v1/chat/completions",
            body={
                "model": "router/auto",
                "messages": [{"role": "user", "content": "hello"}],
            },
            headers={
                "Authorization": "Bearer contract-secret",
                "Origin": "http://allowed.example",
            },
        )
        self.assertEqual(200, status)
        self.assertEqual("tr_http", payload["router_trace_id"])
        self.assertEqual("deepseek/deepseek-v4-pro", payload["model"])
        self.assertEqual("http://allowed.example", headers["Access-Control-Allow-Origin"])

    def test_metrics_endpoint_requires_auth_and_returns_events(self):
        status, payload, _ = self.request(
            "GET",
            "/api/metrics",
            headers={"Authorization": "Bearer contract-secret"},
        )
        self.assertEqual(200, status)
        self.assertIn("requests", payload["metrics"])
        self.assertIsInstance(payload["events"], list)


if __name__ == "__main__":
    unittest.main()
