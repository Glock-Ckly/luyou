from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC_ROOT = ROOT / "specs" / "execution-closure"
SPEC_FILES = (
    "overview.md",
    "job-lifecycle.md",
    "prompt-package.md",
    "model-binding.md",
    "verification.md",
    "artifact-store.md",
    "cost-ledger.md",
    "terminology.md",
)


class ExecutionClosureSpecificationTests(unittest.TestCase):
    def test_overview_indexes_all_execution_closure_specs(self):
        content = (SPEC_ROOT / "overview.md").read_text(encoding="utf-8")
        for filename in SPEC_FILES[1:]:
            self.assertIn(f"]({filename})", content, filename)

    def test_all_execution_closure_specs_exist_and_are_nonempty(self):
        for filename in SPEC_FILES:
            path = SPEC_ROOT / filename
            with self.subTest(filename=filename):
                self.assertTrue(path.is_file(), filename)
                self.assertGreater(len(path.read_text(encoding="utf-8").strip()), 200, filename)

    def test_execution_closure_adrs_have_required_sections(self):
        for number in range(9, 15):
            matches = list((ROOT / "docs" / "adr").glob(f"ADR-{number:03d}-*.md"))
            with self.subTest(adr=number):
                self.assertEqual(1, len(matches), matches)
                content = matches[0].read_text(encoding="utf-8")
                for heading in ("## 背景", "## 决策", "## 后果"):
                    self.assertIn(heading, content)

    def test_key_status_terms_match_governing_definitions_once(self):
        content = (SPEC_ROOT / "terminology.md").read_text(encoding="utf-8")
        definitions = {
            "routed": "已产出 RouteDecision（选定候选模型）",
            "queued": "已投递到队列（Cursor 等），等待外部处理",
            "answered": "模型返回了文本",
            "executed": "执行器完成且返回 ExecutionReceipt",
            "verified": "VerificationReport.status == PASS，7 个必要条件全满足",
            "delivered": "已产出 DeliveryReport 与全部 Artifact，可下载",
        }
        for term, definition in definitions.items():
            with self.subTest(term=term):
                self.assertEqual(1, content.count(f"| `{term}` | {definition} |"))


if __name__ == "__main__":
    unittest.main()
