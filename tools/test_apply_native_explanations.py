"""Tests for the native sentence-explanation SQLite boundary."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "skills" / "batch-japanese-sentence-explanations" / "scripts" / "apply_native_explanations.py"
SPEC = importlib.util.spec_from_file_location("apply_native_explanations", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


VALID_EXPLANATION = (
    "**I remember my youth fondly.**\n\n---\n\n"
    "- **青春（せいしゅん）** — noun, \"youth\" in this sentence. [JLPT N1]\n"
    "- **〜を思い出す** — fixed verb phrase, \"to remember/call to mind\". [JLPT N3]"
)


def create_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE books(code TEXT PRIMARY KEY);
        CREATE TABLE units(book_code TEXT, number INTEGER, header TEXT,
                           PRIMARY KEY(book_code, number));
        CREATE TABLE vocabulary_items(item_id INTEGER PRIMARY KEY, kanji TEXT,
                                      reading TEXT);
        CREATE TABLE book_entries(
          entry_id INTEGER PRIMARY KEY, item_id INTEGER, book_code TEXT,
          unit_number INTEGER, source_index INTEGER, sentence TEXT,
          UNIQUE(book_code, source_index));
        CREATE TABLE item_examples(
          item_id INTEGER, position INTEGER, kind TEXT, text TEXT,
          explanation_md TEXT, PRIMARY KEY(item_id, position));
        INSERT INTO books VALUES ('N1');
        INSERT INTO units VALUES ('N1', 1, 'Test');
        INSERT INTO vocabulary_items VALUES (10, '青春', 'せいしゅん');
        INSERT INTO vocabulary_items VALUES (11, '言いつける', 'いいつける');
        INSERT INTO book_entries VALUES (100, 10, 'N1', 1, 1, '青春時代を懐かしく思い出す。');
        INSERT INTO book_entries VALUES (101, 11, 'N1', 1, 2, '上司は部下に仕事を言いつけて外出した。');
        INSERT INTO item_examples VALUES (10, 0, 'main_sentence', '青春時代を懐かしく思い出す。', '');
        INSERT INTO item_examples VALUES (11, 3, 'example_sentence', '上司は部下に仕事を言いつけて外出した。', NULL);
        """
    )
    conn.commit()
    conn.close()


class ApplyNativeExplanationsTests(unittest.TestCase):
    def test_validates_and_applies_nonzero_shared_example_position(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "n2vocab.sqlite"
            create_db(db)
            records = [
                {
                    "source_index": 2,
                    "item_id": 11,
                    "position": 3,
                    "sentence": "上司は部下に仕事を言いつけて外出した。",
                    "new_explanation_md": VALID_EXPLANATION,
                }
            ]
            summary = MODULE.apply_records(db, records, root / "output", "N1")
            self.assertEqual(summary["changed_rows"], 1)
            conn = sqlite3.connect(db)
            self.assertEqual(
                conn.execute(
                    "SELECT explanation_md FROM item_examples WHERE item_id=11 AND position=3"
                ).fetchone()[0],
                VALID_EXPLANATION,
            )
            conn.close()
            self.assertTrue(list((root / "output").glob("*.bak")))

    def test_rejects_sentence_identity_mismatch_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "n2vocab.sqlite"
            create_db(db)
            records = [
                {
                    "source_index": 1,
                    "item_id": 10,
                    "position": 0,
                    "sentence": "別の文。",
                    "new_explanation_md": VALID_EXPLANATION,
                }
            ]
            with self.assertRaises(MODULE.NativeExplanationError):
                MODULE.apply_records(db, records, root / "output", "N1")
            conn = sqlite3.connect(db)
            self.assertEqual(
                conn.execute(
                    "SELECT explanation_md FROM item_examples WHERE item_id=10 AND position=0"
                ).fetchone()[0],
                "",
            )
            conn.close()

    def test_refuses_existing_explanation_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "n2vocab.sqlite"
            create_db(db)
            conn = sqlite3.connect(db)
            conn.execute(
                "UPDATE item_examples SET explanation_md=? WHERE item_id=10 AND position=0",
                ("existing",),
            )
            conn.commit()
            conn.close()
            records = [
                {
                    "source_index": 1,
                    "item_id": 10,
                    "position": 0,
                    "sentence": "青春時代を懐かしく思い出す。",
                    "new_explanation_md": VALID_EXPLANATION,
                }
            ]
            with self.assertRaises(MODULE.NativeExplanationError):
                MODULE.apply_records(db, records, root / "output", "N1")

    def test_rejects_source_provenance_in_learner_explanation(self) -> None:
        with self.assertRaises(MODULE.NativeExplanationError):
            MODULE.validate_markdown(
                VALID_EXPLANATION + "\n- **Source:** N1語彙トレーニング, page 1.",
                1,
            )


if __name__ == "__main__":
    unittest.main()
