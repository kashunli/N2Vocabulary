from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from import_green_word_book import display_word, import_green_word_book


class GreenWordBookImportTests(unittest.TestCase):
    def test_display_word_recovers_bracket_form_from_reading(self) -> None:
        self.assertEqual(
            display_word(
                {"headword": "けずる", "bracket_form": "", "reading": "【削る】"}
            ),
            ("削る", "けずる"),
        )
        self.assertEqual(
            display_word(
                {"headword": "オン", "bracket_form": "", "reading": "[on]"}
            ),
            ("on", "オン"),
        )

    def test_display_word_keeps_language_origin_as_reading(self) -> None:
        self.assertEqual(
            display_word(
                {"headword": "ズボン", "bracket_form": "【法 jupon】", "reading": ""}
            ),
            ("ズボン", "法 jupon"),
        )
        self.assertEqual(
            display_word(
                {"headword": "コーヒー", "bracket_form": "", "reading": "【荷 koffie】"}
            ),
            ("コーヒー", "荷 koffie"),
        )

    def test_import_maps_source_rows_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "n2vocab.sqlite"
            green_root = root / "greenWordBook"
            create_schema(db_path)
            write_green_fixture(green_root)

            first = import_green_word_book(db_path, green_root)
            second = import_green_word_book(db_path, green_root)

            self.assertEqual(first["words_imported"], 4)
            self.assertEqual(second["words_imported"], 4)
            self.assertEqual(first["unit_counts"], {"1": 1, "2": 3})
            self.assertEqual(first["needs_review_count"], 1)
            self.assertEqual(first["needs_review_ids"], ["dup-id"])
            self.assertEqual(first["unit_derivation_sources"], {"page_manifest": 3, "record_section": 1})

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            try:
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM entries WHERE book_code = 'GWB_N2'").fetchone()[0],
                    4,
                )
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM entry_examples").fetchone()[0],
                    2,
                )

                row_one = conn.execute(
                    "SELECT source_index, unit_number, kanji, reading, meaning_zh, sentence FROM entries WHERE source_index = 1"
                ).fetchone()
                self.assertEqual(dict(row_one), {
                    "source_index": 1,
                    "unit_number": 1,
                    "kanji": "相変わらず",
                    "reading": "あいかわらず",
                    "meaning_zh": "依旧",
                    "sentence": "相変わらず元気だ。",
                })

                row_two = conn.execute(
                    "SELECT source_index, unit_number, kanji, reading, explanation_md FROM entries WHERE source_index = 2"
                ).fetchone()
                self.assertEqual(row_two["unit_number"], 2)
                self.assertEqual(row_two["kanji"], "くどい")
                self.assertEqual(row_two["reading"], "")
                self.assertIn("**Needs review:**", row_two["explanation_md"])
                self.assertIn("### Exam Questions", row_two["explanation_md"])
                self.assertIn("1997年2級", row_two["explanation_md"])
                self.assertNotIn("**Source index:**", row_two["explanation_md"])

                row_three = conn.execute(
                    "SELECT source_index, unit_number, kanji, meaning_zh FROM entries WHERE source_index = 3"
                ).fetchone()
                self.assertEqual(row_three["source_index"], 3)
                self.assertEqual(row_three["unit_number"], 2)
                self.assertEqual(row_three["kanji"], "青空")
                self.assertEqual(row_three["meaning_zh"], "")

                loanword = conn.execute(
                    "SELECT kanji, reading, explanation_md FROM entries WHERE source_index = 4"
                ).fetchone()
                self.assertEqual(loanword["kanji"], "ice cream")
                self.assertEqual(loanword["reading"], "アイスクリーム")
                self.assertEqual(loanword["explanation_md"], "")
            finally:
                conn.close()


def create_schema(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE books (
          code TEXT PRIMARY KEY,
          title TEXT NOT NULL,
          notes TEXT
        );
        CREATE TABLE units (
          book_code TEXT NOT NULL REFERENCES books(code),
          number INTEGER NOT NULL,
          header TEXT NOT NULL,
          title TEXT NOT NULL,
          PRIMARY KEY(book_code, number)
        );
        CREATE TABLE entries (
          entry_id INTEGER PRIMARY KEY,
          uuid TEXT NOT NULL UNIQUE,
          book_code TEXT NOT NULL,
          unit_number INTEGER NOT NULL,
          source_index INTEGER NOT NULL,
          position INTEGER NOT NULL,
          kanji TEXT NOT NULL,
          reading TEXT,
          verb_pattern TEXT,
          meaning_en TEXT,
          meaning_zh TEXT,
          sentence TEXT,
          explanation_md TEXT,
          word_clip TEXT,
          sentence_clip TEXT,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(book_code, source_index),
          FOREIGN KEY(book_code, unit_number) REFERENCES units(book_code, number)
        );
        CREATE TABLE entry_examples (
          entry_id INTEGER NOT NULL REFERENCES entries(entry_id) ON DELETE CASCADE,
          position INTEGER NOT NULL,
          kind TEXT NOT NULL DEFAULT 'example_sentence',
          text TEXT NOT NULL,
          reading TEXT,
          translation_en TEXT,
          translation_zh TEXT,
          explanation_md TEXT,
          audio_clip TEXT,
          category TEXT,
          PRIMARY KEY(entry_id, position)
        );
        CREATE TABLE word_marks (
          entry_id INTEGER PRIMARY KEY REFERENCES entries(entry_id) ON DELETE CASCADE,
          known INTEGER NOT NULL DEFAULT 0,
          flagged INTEGER NOT NULL DEFAULT 0,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.close()


def write_green_fixture(green_root: Path) -> None:
    (green_root / "data").mkdir(parents=True)
    (green_root / "material").mkdir(parents=True)
    (green_root / "material" / "page_manifest.json").write_text(
        json.dumps(
            {
                "pages": [
                    {"source_pdf_page": 9, "title": "第1单元", "section": "必考词"},
                    {"source_pdf_page": 10, "title": "第2单元", "section": "必考词"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (green_root / "data" / "green_word_book_n2_vocab.json").write_text(
        json.dumps(
            {
                "records": [
                    {
                        "id": "dup-id",
                        "entry_number": "001",
                        "source_pdf_page": 9,
                        "book_page": 1,
                        "section": "必考词",
                        "headword": "あいかわらず",
                        "reading": "",
                        "accent": "0",
                        "bracket_form": "【相変わらず】",
                        "part_of_speech": "（副）",
                        "chinese_meaning": "依旧",
                        "example_japanese": "相変わらず元気だ。",
                        "example_chinese": "还是很精神。",
                        "near_synonyms": ["依然"],
                    },
                    {
                        "id": "dup-id",
                        "entry_number": "001",
                        "source_pdf_page": 999,
                        "book_page": 2,
                        "section": "新日语能力考试 N2 词汇 ▲ 必考词 (第 2 单元)",
                        "headword": "くどい",
                        "reading": "",
                        "accent": "",
                        "bracket_form": "",
                        "part_of_speech": "",
                        "chinese_meaning": "啰嗦",
                        "example_japanese": "説明がくどい。",
                        "example_chinese": "说明很啰嗦。",
                        "needs_review": True,
                        "exam_questions": [
                            {
                                "question_japanese": "彼の説明は____。",
                                "year_level": "1997年2級",
                                "choices": ["1.くどい", "2.あまい"],
                                "analysis_chinese": "答案是1。",
                            }
                        ],
                    },
                    {
                        "id": "bad-number",
                        "entry_number": "",
                        "source_pdf_page": 10,
                        "book_page": 2,
                        "section": "",
                        "headword": "あおぞら",
                        "reading": "",
                        "bracket_form": "【青空】",
                        "chinese_meaning": "",
                    },
                    {
                        "id": "loanword",
                        "entry_number": "0002",
                        "source_pdf_page": 10,
                        "book_page": 2,
                        "section": "",
                        "headword": "アイスクリーム",
                        "reading": "",
                        "bracket_form": "【ice cream】",
                        "chinese_meaning": "冰淇淋",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
