from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_review_decisions.py"
SPEC = importlib.util.spec_from_file_location("validate_review_decisions", SCRIPT)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


class ReviewValidationTests(unittest.TestCase):
    def test_normalizes_noop_and_applies_audio_problem(self) -> None:
        evidence = [
            {
                "source_index": 233,
                "expected": "借金を返すには、休日も働くよりほかにしかたない。",
                "audio_clip": "clips/sentences/sentence233.mp3",
            },
            {
                "source_index": 1147,
                "expected": "三日前に出した手紙がいまだに着かないのはおかしい。",
                "audio_clip": "clips/sentences/sentence1147.mp3",
            },
        ]
        decisions = [
            {
                "source_index": row["source_index"],
                "unit": 1,
                "headword": "test",
                "decision": "replace",
                "original_text": row["expected"],
                "replacement_text": row["expected"],
                "audio_clip": row["audio_clip"],
                "note": "",
            }
            for row in evidence
        ]
        review = {"version": 1, "source_sha256": "signed", "decisions": decisions}

        normalized, report = validator.validate_and_normalize(
            review, evidence, "signed", {233}
        )

        by_id = {row["source_index"]: row for row in normalized["decisions"]}
        self.assertEqual(by_id[233]["decision"], "audio_problem")
        self.assertEqual(by_id[1147]["decision"], "keep")
        self.assertEqual(report["normalized_noop_replacements"], [233, 1147])
        self.assertEqual(report["audio_problem_overrides"], [233])
        self.assertEqual(report["status"], "valid_complete")


if __name__ == "__main__":
    unittest.main()
