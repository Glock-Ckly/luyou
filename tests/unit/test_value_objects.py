from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from model_router.domain.models import ModelId, ProviderId, TraceId


class ValueObjectTests(unittest.TestCase):
    def test_model_id_round_trip(self):
        model = ModelId.parse("openai/gpt-5.4")
        self.assertEqual(ProviderId("openai"), model.provider_id)
        self.assertEqual("gpt-5.4", model.name)
        self.assertEqual("openai/gpt-5.4", model.value)

    def test_invalid_model_id_is_rejected(self):
        with self.assertRaises(ValueError):
            ModelId.parse("missing-provider")

    def test_trace_id_has_stable_prefix(self):
        self.assertTrue(TraceId.new().value.startswith("tr_"))


if __name__ == "__main__":
    unittest.main()

