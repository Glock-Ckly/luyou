#!/usr/bin/env python3
"""Five-page dashboard API and artifact checks."""

from __future__ import annotations

import unittest
from pathlib import Path

from dashboard_server import build_catalog, build_specs, simulate_reliability

ROOT = Path(__file__).resolve().parent.parent


class DashboardDemoTests(unittest.TestCase):
    def test_five_pages_and_shared_assets_exist(self):
        expected = [
            "index.html",
            "routing.html",
            "providers.html",
            "reliability.html",
            "architecture.html",
            "assets/styles.css",
            "assets/app.js",
        ]
        for relative_path in expected:
            self.assertTrue((ROOT / "dashboard" / relative_path).is_file(), relative_path)

    def test_catalog_is_generated_from_runtime_routing_data(self):
        catalog = build_catalog()
        self.assertGreaterEqual(len(catalog["providers"]), 3)
        self.assertGreaterEqual(len(catalog["models"]), 5)
        self.assertGreater(len(catalog["routes"]), 0)
        self.assertTrue(all(model["provider"] for model in catalog["models"]))

    def test_specs_cover_domain_and_failure_boundaries(self):
        specs = build_specs()
        domain_names = {domain["name"] for domain in specs["domains"]}
        self.assertTrue({"Gateway", "Routing", "Provider", "Execution"}.issubset(domain_names))
        self.assertIn("FALLBACK", specs["failure_lifecycle"])

    def test_retryable_failure_falls_back_to_next_candidate(self):
        baseline = simulate_reliability({"task_type": "implementation", "complexity": "T2"})
        primary = baseline["candidate_chain"][0]
        result = simulate_reliability({
            "task_type": "implementation",
            "complexity": "T2",
            "failure_mode": "timeout",
            "retry_once": True,
            "failed_models": [primary],
        })
        self.assertEqual("success", result["outcome"])
        self.assertNotEqual(primary, result["selected_model"])
        self.assertEqual(["retry", "fallback"], [attempt["action"] for attempt in result["attempts"][:2]])

    def test_authentication_failure_is_fail_fast(self):
        baseline = simulate_reliability({"task_type": "architecture", "complexity": "T4"})
        primary = baseline["candidate_chain"][0]
        result = simulate_reliability({
            "task_type": "architecture",
            "complexity": "T4",
            "failure_mode": "authentication",
            "failed_models": [primary],
        })
        self.assertEqual("all_providers_failed", result["outcome"])
        self.assertEqual(1, len(result["attempts"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
