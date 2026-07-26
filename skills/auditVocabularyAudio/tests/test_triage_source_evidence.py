from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import triage_source_evidence as triage


class SourceEvidenceTests(unittest.TestCase):
    def test_best_line_compares_kanji_and_kana_phonetically(self) -> None:
        block = (
            "1127 いきいき\n"
            "・ 彼女はいきいきと働いている。 "
            "・ 子どもたちの表情が印象的だった。"
        )
        score, line = triage.best_line(block, "彼女は生き生きと働いている")
        self.assertEqual(score, 1.0)
        self.assertEqual(line, "彼女はいきいきと働いている。")

    def test_audio_and_raw_ocr_agreement_is_source_confirmed(self) -> None:
        audit = {
            "items": [
                {
                    "source_index": 1118,
                    "unit_number": 13,
                    "headword": "続々（と）",
                    "comparisons": {
                        "sentence": {
                            "status": "review",
                            "score": 0.95,
                            "expected": "客が続々と訪めかけた。",
                            "transcript": "客が続々と詰めかけた。",
                            "audio_clip": "sentence1118.mp3",
                        }
                    },
                }
            ]
        }
        blocks = {
            1118: {"page": "page_244.json", "block": "1118 ぞくぞく\n・ 客が続々と詰めかけた。"}
        }
        rows = triage.build_evidence(audit, blocks, 0.90, 0.04)
        self.assertEqual(rows[0]["classification"], "source_confirmed")
        self.assertEqual(rows[0]["asr_vs_raw"], 1.0)


if __name__ == "__main__":
    unittest.main()
