from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from model_router.adapters.http.gateway import (
    GatewayConfig,
    GatewayRequestError,
    InMemoryRateLimiter,
    authorize,
    format_chat_completion,
    parse_chat_completion,
    resolve_workdir,
    safe_error_payload,
)


class HttpGatewayContractTests(unittest.TestCase):
    def test_bearer_token_is_required_when_configured(self):
        config = GatewayConfig(api_token="secret")
        with self.assertRaises(GatewayRequestError) as caught:
            authorize({}, config)
        self.assertEqual(401, caught.exception.status)
        authorize({"Authorization": "Bearer secret"}, config)

    def test_chat_messages_become_a_stable_prompt(self):
        prompt, requested_model = parse_chat_completion(
            {
                "model": "router/auto",
                "messages": [
                    {"role": "system", "content": "Be precise"},
                    {"role": "user", "content": "Design a cache"},
                ],
            }
        )
        self.assertIn("system: Be precise", prompt)
        self.assertIn("user: Design a cache", prompt)
        self.assertEqual("router/auto", requested_model)

    def test_workdir_cannot_escape_allowed_roots(self):
        with tempfile.TemporaryDirectory() as allowed, tempfile.TemporaryDirectory() as outside:
            config = GatewayConfig(allowed_workdirs=(Path(allowed).resolve(),))
            self.assertEqual(Path(allowed).resolve(), resolve_workdir(allowed, config))
            with self.assertRaises(GatewayRequestError) as caught:
                resolve_workdir(outside, config)
            self.assertEqual(403, caught.exception.status)

    def test_openai_response_uses_actual_route_result(self):
        payload = format_chat_completion(
            {
                "trace_id": "tr_contract",
                "selected_model": "openai/gpt-5.4",
                "result": "completed",
            },
            requested_model="router/auto",
        )
        self.assertEqual("chat.completion", payload["object"])
        self.assertEqual("openai/gpt-5.4", payload["model"])
        self.assertEqual("completed", payload["choices"][0]["message"]["content"])
        self.assertEqual("tr_contract", payload["router_trace_id"])

    def test_internal_errors_do_not_leak_exception_text(self):
        status, payload = safe_error_payload(RuntimeError("API_KEY=top-secret"))
        self.assertEqual(500, status)
        self.assertNotIn("top-secret", str(payload))
        self.assertEqual("internal_error", payload["error"]["code"])

    def test_rate_limit_returns_normalized_429(self):
        limiter = InMemoryRateLimiter()
        config = GatewayConfig(rate_limit_per_minute=2)
        limiter.check("client-a", config, now=100)
        limiter.check("client-a", config, now=101)
        with self.assertRaises(GatewayRequestError) as caught:
            limiter.check("client-a", config, now=102)
        self.assertEqual(429, caught.exception.status)
        self.assertEqual("rate_limit_exceeded", caught.exception.code)
        limiter.check("client-a", config, now=161)


if __name__ == "__main__":
    unittest.main()
