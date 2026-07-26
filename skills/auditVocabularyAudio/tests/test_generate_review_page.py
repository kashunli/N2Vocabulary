from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_review_page.py"
SPEC = importlib.util.spec_from_file_location("generate_review_page", SCRIPT)
assert SPEC and SPEC.loader
review = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = review
SPEC.loader.exec_module(review)


class ReviewPageTests(unittest.TestCase):
    def test_page_embeds_decisions_and_relative_audio(self) -> None:
        output = review.ROOT / "work" / "vocabulary_audio_audit" / "n2_all_both" / "review.html"
        rows = [
            {
                "source_index": 1118,
                "unit": 13,
                "headword": "続々（と）",
                "classification": "source_confirmed",
                "audit_score": 0.95,
                "expected": "客が続々と訪めかけた。",
                "transcript": "客が続々と詰めかけた。",
                "raw_line": "客が続々と詰めかけた。",
                "asr_vs_raw": 1.0,
                "db_vs_raw": 0.95,
                "evidence_margin": 0.05,
                "raw_page": "page_244.json",
                "audio_clip": "clips/sentences/sentence1118.mp3",
            }
        ]
        html = review.build_review_html(rows, "abc123", output)
        self.assertIn("N2 vocabulary audio review", html)
        self.assertIn("Accept replacement", html)
        self.assertIn("Keep original", html)
        self.assertIn("Save custom text", html)
        self.assertIn("localStorage", html)
        self.assertIn("../../../clips/sentences/sentence1118.mp3", html)
        self.assertIn("続々（と）", html)
        self.assertIn('id="emptyState"', html)

    def test_script_payload_escapes_html_closing_tags(self) -> None:
        payload = review.safe_json_for_script({"text": "</script>"})
        self.assertNotIn("</script>", payload)
        self.assertIn("\\u003c/script>", payload)


if __name__ == "__main__":
    unittest.main()
