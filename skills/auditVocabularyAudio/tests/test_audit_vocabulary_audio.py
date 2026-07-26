from __future__ import annotations

import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_vocabulary_audio.py"
SPEC = importlib.util.spec_from_file_location("audit_vocabulary_audio", SCRIPT)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


class TextComparisonTests(unittest.TestCase):
    def test_reported_ocr_error_is_not_hidden_inside_long_sentence(self) -> None:
        result = audit.compare(
            "客が続々と訪めかけ、会場はすぐに満員になった。",
            "客が続々と詰めかけ、会場はすぐにマインになった",
            threshold=0.96,
        )
        self.assertEqual(result["status"], "review")
        self.assertIn("→", result["phonetic_diff"])

    def test_punctuation_only_difference_passes(self) -> None:
        result = audit.compare("今日は晴れです。", "今日は晴れです", threshold=0.96)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["score"], 1.0)

    def test_empty_asr_is_explicit(self) -> None:
        result = audit.compare("続々と来た。", "", threshold=0.96)
        self.assertEqual(result["status"], "asr_empty")


class CanonicalQueryTests(unittest.TestCase):
    def test_load_items_uses_main_sentence_and_source_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "test.sqlite"
            connection = sqlite3.connect(db)
            connection.executescript(
                """
                CREATE TABLE vocabulary_items (
                    item_id INTEGER PRIMARY KEY, kanji TEXT, reading TEXT, word_clip TEXT
                );
                CREATE TABLE book_entries (
                    entry_id INTEGER PRIMARY KEY, item_id INTEGER, book_code TEXT,
                    source_index INTEGER, unit_number INTEGER, position INTEGER,
                    word_clip TEXT, sentence_clip TEXT
                );
                CREATE TABLE item_examples (
                    item_id INTEGER, position INTEGER, kind TEXT, text TEXT, audio_clip TEXT
                );
                CREATE TABLE item_example_sources (
                    item_id INTEGER, position INTEGER, source_book_code TEXT, source_index INTEGER
                );
                INSERT INTO vocabulary_items VALUES (1, '続々（と）', 'ぞくぞく（と）', 'clips/words/word1118.mp3');
                INSERT INTO book_entries VALUES (99, 1, 'N2', 1118, 13, 28, NULL, 'legacy.mp3');
                INSERT INTO item_examples VALUES (1, 0, 'main_sentence', '主例文。', 'human.mp3');
                INSERT INTO item_examples VALUES (1, 1, 'example_sentence', '追加例文。', 'tts.mp3');
                INSERT INTO item_examples VALUES (1, 2, 'main_sentence', '別の配置の主例文。', 'other.mp3');
                INSERT INTO item_example_sources VALUES (1, 0, 'N2', 1118);
                INSERT INTO item_example_sources VALUES (1, 1, 'N2', 1118);
                INSERT INTO item_example_sources VALUES (1, 2, 'N2', 999);
                """
            )
            connection.close()

            items = audit.load_items(db, "N2", unit=13)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].source_index, 1118)
            self.assertEqual(items[0].sentence, "主例文。")
            self.assertEqual(items[0].sentence_clip, "human.mp3")


if __name__ == "__main__":
    unittest.main()
