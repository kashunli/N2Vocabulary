from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from import_n2_must_1500 import clean_headword, import_rows, parse_entries
from test_import_green_word_book import create_schema


class N2Must1500Tests(unittest.TestCase):
    def test_parse_entries_handles_page_break_and_related_forms(self) -> None:
        rows = parse_entries(
            [
                (1, "あいじょう【愛情】 ⓪"),
                (1, "［名］ 爱，爱情；热爱"),
                (1, "連 母の愛情（母爱）"),
                (1, "メモ (memo) ①"),
                (2, "［名］ 笔记；记录"),
            ]
        )
        self.assertEqual(rows[0]["headword"], "愛情")
        self.assertEqual(rows[0]["reading"], "あいじょう")
        self.assertEqual(rows[0]["related"], ["連 母の愛情（母爱）"])
        self.assertEqual(rows[1]["headword"], "メモ")
        self.assertEqual(rows[1]["source_page"], 1)

    def test_headword_cleanup_preserves_source_form(self) -> None:
        row = clean_headword("マイペース (〈和〉my+pace) ③")
        self.assertEqual(row["headword"], "マイペース")
        self.assertEqual(row["reading"], "マイペース")
        self.assertEqual(row["accent"], "③")

    def test_import_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.sqlite"
            create_schema(db_path)
            entries = []
            for index in range(1, 1489):
                entries.append(
                    {
                        "source_index": index,
                        "source_page": 1,
                        "section": "名词",
                        "headword": f"語{index}",
                        "reading": f"ご{index}",
                        "accent": "⓪",
                        "source_headword": f"ご{index}【語{index}】",
                        "part_of_speech": "名",
                        "meaning_en": "affection; love" if index == 1 else "",
                        "meaning_zh": f"词{index}",
                        "related": ["合 園芸植物 [しょくぶつ]（园艺作物）"] if index == 1 else [],
                    }
                )
            payload = {"entries": entries}
            import_rows(db_path, payload)
            import_rows(db_path, payload)
            connection = sqlite3.connect(db_path)
            connection.row_factory = sqlite3.Row
            try:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM entries WHERE book_code='N2_1500'").fetchone()[0],
                    1488,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT meaning_en FROM entries WHERE book_code='N2_1500' AND source_index=1"
                    ).fetchone()[0],
                    "affection; love",
                )
                explanation = connection.execute(
                    "SELECT explanation_md FROM entries WHERE book_code='N2_1500' AND source_index=1"
                ).fetchone()[0]
                self.assertNotIn("Related forms", explanation)
                related = connection.execute(
                    """
                    SELECT ex.position, ex.kind, ex.text, ex.reading, ex.translation_zh, ex.category
                    FROM entry_examples ex
                    JOIN entries e ON e.entry_id = ex.entry_id
                    WHERE e.book_code='N2_1500' AND e.source_index=1
                    """
                ).fetchone()
                self.assertEqual(dict(related), {
                    "position": 1,
                    "kind": "related_term",
                    "text": "園芸植物",
                    "reading": "しょくぶつ",
                    "translation_zh": "园艺作物",
                    "category": "合",
                })
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
