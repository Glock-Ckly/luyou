#!/usr/bin/env python3
"""Dashboard API, artifact and documentation checks."""

from __future__ import annotations

import unittest
from pathlib import Path

from dashboard_server import build_catalog, build_specs, simulate_reliability

ROOT = Path(__file__).resolve().parent.parent


class DashboardDemoTests(unittest.TestCase):
    def test_pages_and_shared_assets_exist(self):
        expected = [
            "index.html",
            "routing.html",
            "providers.html",
            "reliability.html",
            "architecture.html",
            "tasks.html",
            "assets/styles.css",
            "assets/app.js",
        ]
        for relative_path in expected:
            self.assertTrue((ROOT / "dashboard" / relative_path).is_file(), relative_path)

    def test_task_workbench_has_live_crud_and_nested_layout(self):
        page = ROOT / "dashboard" / "tasks.html"
        self.assertTrue(page.is_file())
        content = page.read_text(encoding="utf-8")
        script = (ROOT / "dashboard" / "assets" / "app.js").read_text(encoding="utf-8")
        styles = (ROOT / "dashboard" / "assets" / "styles.css").read_text(encoding="utf-8")
        for marker in (
            "task-workbench",
            "task-category-rail",
            "task-market-main",
            "task-context-panel",
            "task-create",
            "task-form",
            "task-delete",
        ):
            self.assertIn(marker, content + script + styles)
        self.assertIn("/api/tasks", script)
        self.assertIn("'POST'", script)
        self.assertIn("'PUT'", script)
        self.assertIn("method: 'DELETE'", script)

    def test_task_workbench_has_goal_first_planning_and_connection_recovery(self):
        page = (ROOT / "dashboard" / "tasks.html").read_text(encoding="utf-8")
        script = (ROOT / "dashboard" / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("<header data-header>", page)
        for marker in (
            "task-goal",
            "task-analyze",
            "task-analysis-preview",
            "task-subtasks",
            "task-model-recommendations",
            "task-plan-link",
            "/api/tasks/analyze",
            "/api/tasks/from-analysis",
            "model_router_api_token",
            "retryWithToken",
        ):
            self.assertIn(marker, page + script)

    def test_pages_are_readable_and_use_live_runtime_data(self):
        expected_titles = {
            "index.html": "系统总览",
            "routing.html": "路由实验室",
            "providers.html": "Provider 目录",
            "reliability.html": "可靠性实验室",
            "architecture.html": "架构与规格",
            "tasks.html": "任务工作台",
        }
        for filename, title in expected_titles.items():
            content = (ROOT / "dashboard" / filename).read_text(encoding="utf-8")
            self.assertIn(title, content)
            self.assertNotIn("鎬", content)
        script = (ROOT / "dashboard" / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertIn("/api/metrics", script)
        self.assertIn("trace_id", script)
        self.assertIn("attempts", script)

    def test_container_delivery_files_exist(self):
        for filename in ["Dockerfile", "compose.yaml", ".dockerignore"]:
            self.assertTrue((ROOT / filename).is_file(), filename)

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
        self.assertEqual(result["trace_id"], result["execution_trace_id"])

    def test_authentication_failure_is_fail_fast(self):
        baseline = simulate_reliability({"task_type": "architecture", "complexity": "T4"})
        primary = baseline["candidate_chain"][0]
        result = simulate_reliability({
            "task_type": "architecture",
            "complexity": "T4",
            "failure_mode": "authentication",
            "failed_models": [primary],
        })
        self.assertEqual("failed", result["outcome"])
        self.assertEqual("provider_authentication", result["final_error_type"])
        self.assertEqual(1, len(result["attempts"]))

    def test_repository_documents_match_page_and_test_counts(self):
        offline_count = unittest.defaultTestLoader.discover(str(ROOT / "tests")).countTestCases()
        dashboard_count = unittest.defaultTestLoader.loadTestsFromTestCase(
            DashboardDemoTests
        ).countTestCases()
        for filename in ("README.md", "STATUS.md", "docs/checklist-matrix.md"):
            content = (ROOT / filename).read_text(encoding="utf-8")
            self.assertIn("六页", content, filename)
            self.assertIn(f"{offline_count}/{offline_count}", content, filename)
            self.assertIn(f"{dashboard_count}/{dashboard_count}", content, filename)


if __name__ == "__main__":
    unittest.main(verbosity=2)
