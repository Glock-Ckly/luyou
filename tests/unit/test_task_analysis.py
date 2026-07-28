from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from model_router.domain.task_analysis import TaskAnalysis, TaskAnalysisError
from model_router.domain.model_capabilities import build_planning_model_catalog


def valid_analysis() -> dict:
    return {
        "goal_summary": "Build a secure API",
        "suggested_title": "Secure API",
        "description": "Implement and verify a secure API",
        "task_type": "implementation",
        "complexity": "T3",
        "priority": "high",
        "technology_stack": ["Python", "FastAPI", "PostgreSQL"],
        "scope": "",
        "coverage_target_percent": 95,
        "acceptance_criteria": [
            {
                "category": "functional",
                "criterion": "All documented endpoints satisfy their contracts",
                "target_percent": 100,
                "verification": "Run contract tests",
            }
        ],
        "tags": ["api", "security", "api"],
        "split_recommended": True,
        "subtasks": [
            {
                "title": "Design API",
                "description": "Define contracts",
                "task_type": "architecture",
                "complexity": "T2",
                "technology_stack": ["OpenAPI"],
                "acceptance_criteria": ["All endpoints are specified"],
                "recommended_model": "anthropic/claude-sonnet-4-6",
                "fallback_models": ["openai/gpt-5.4"],
                "binding_mode": "EXECUTOR_MANAGED",
            },
            {
                "title": "Implement API",
                "description": "Implement contracts",
                "task_type": "implementation",
                "complexity": "T3",
                "technology_stack": ["Python", "FastAPI"],
                "acceptance_criteria": ["95 percent coverage"],
                "recommended_model": "openai/gpt-5.3-codex",
                "fallback_models": [],
                "binding_mode": "EXECUTOR_MANAGED",
            },
        ],
        "needs_clarification": False,
        "clarification_questions": [],
        "recommended_models": [
            {
                "model_id": "openai/gpt-5.3-codex",
                "role": "implementation",
                "reason": "Repository tools",
                "strengths": ["code"],
                "limitations": ["binding not enforced"],
                "binding_mode": "EXECUTOR_MANAGED",
            }
        ],
        "risks": ["Authentication edge cases"],
        "reasoning": "The task spans design and implementation",
    }


class TaskAnalysisTests(unittest.TestCase):
    def test_planning_catalog_exposes_model_strengths_and_boundaries(self):
        catalog = build_planning_model_catalog(
            {
                "openai/gpt-5.3-codex": {
                    "tier": "workhorse",
                    "cost_per_mtok": {"in": 1.75, "out": 14.0},
                }
            }
        )
        self.assertIn("repository implementation", catalog[0]["strengths"])
        self.assertIn("execution environment controls actual model binding", catalog[0]["limitations"])
        self.assertEqual("EXECUTOR_MANAGED", catalog[0]["binding_mode"])

    def test_valid_analysis_normalizes_open_technology_stack_and_tags(self):
        analysis = TaskAnalysis.from_dict(
            valid_analysis(), allowed_models={"anthropic/claude-sonnet-4-6", "openai/gpt-5.4", "openai/gpt-5.3-codex"}
        )
        self.assertEqual(("Python", "FastAPI", "PostgreSQL"), analysis.technology_stack)
        self.assertEqual(("api", "security"), analysis.tags)

    def test_scope_is_optional_and_status_is_assigned_deterministically(self):
        values = valid_analysis()
        values.pop("scope")
        analysis = TaskAnalysis.from_dict(values, allowed_models={"anthropic/claude-sonnet-4-6", "openai/gpt-5.4", "openai/gpt-5.3-codex"})
        self.assertEqual("", analysis.scope)
        self.assertEqual("ready", analysis.initial_status)

    def test_clarification_maps_to_draft(self):
        values = valid_analysis()
        values["needs_clarification"] = True
        values["clarification_questions"] = ["Which database is required?"]
        analysis = TaskAnalysis.from_dict(values, allowed_models={"anthropic/claude-sonnet-4-6", "openai/gpt-5.4", "openai/gpt-5.3-codex"})
        self.assertEqual("draft", analysis.initial_status)

    def test_unknown_task_type_is_rejected(self):
        values = valid_analysis()
        values["task_type"] = "magic"
        with self.assertRaises(TaskAnalysisError):
            TaskAnalysis.from_dict(values, allowed_models={"anthropic/claude-sonnet-4-6", "openai/gpt-5.4", "openai/gpt-5.3-codex"})

    def test_invalid_coverage_target_is_rejected(self):
        values = valid_analysis()
        values["coverage_target_percent"] = 101
        with self.assertRaises(TaskAnalysisError):
            TaskAnalysis.from_dict(values, allowed_models={"anthropic/claude-sonnet-4-6", "openai/gpt-5.4", "openai/gpt-5.3-codex"})

    def test_unknown_model_recommendation_is_rejected(self):
        values = valid_analysis()
        values["recommended_models"][0]["model_id"] = "unknown/model"
        with self.assertRaises(TaskAnalysisError):
            TaskAnalysis.from_dict(values, allowed_models={"anthropic/claude-sonnet-4-6", "openai/gpt-5.4", "openai/gpt-5.3-codex"})

    def test_analysis_cannot_claim_enforced_model_binding(self):
        values = valid_analysis()
        values["recommended_models"][0]["binding_mode"] = "ENFORCED"
        with self.assertRaises(TaskAnalysisError):
            TaskAnalysis.from_dict(
                values,
                allowed_models={"anthropic/claude-sonnet-4-6", "openai/gpt-5.4", "openai/gpt-5.3-codex"},
            )

    def test_split_requires_two_to_twelve_subtasks(self):
        values = valid_analysis()
        values["subtasks"] = values["subtasks"][:1]
        with self.assertRaises(TaskAnalysisError):
            TaskAnalysis.from_dict(values, allowed_models={"anthropic/claude-sonnet-4-6", "openai/gpt-5.4", "openai/gpt-5.3-codex"})

    def test_markdown_and_hash_are_deterministic(self):
        allowed = {"anthropic/claude-sonnet-4-6", "openai/gpt-5.4", "openai/gpt-5.3-codex"}
        first = TaskAnalysis.from_dict(valid_analysis(), allowed_models=allowed)
        second = TaskAnalysis.from_dict(valid_analysis(), allowed_models=allowed)
        self.assertEqual(first.content_hash, second.content_hash)
        self.assertEqual(first.analysis_id, second.analysis_id)
        self.assertEqual(first.to_markdown(), second.to_markdown())
        self.assertIn("## 验收标准", first.to_markdown())


if __name__ == "__main__":
    unittest.main()
