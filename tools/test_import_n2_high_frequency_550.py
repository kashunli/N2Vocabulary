from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from import_n2_high_frequency_550 import BOOK_CODE, import_rows, parse_text


class N2HighFrequency550Tests(unittest.TestCase):
    def test_parse_text_ignores_split_occurrence_badges(self) -> None:
        text = """
        动词（ ）
        1. 扱う（あつかう） 【他：～を】 【出现次数 16】
        1）处理：この問題を扱う。（处理这个问题。）
        注意：常考搭配。
        2.
        表す（あらわす） 【他：～を】 【出现次数
        17
        】
        1）表示，表现，表达：自分の考えを表す。（表达自己的想法。）
        """
        rows = parse_text(text)
        self.assertEqual(rows[0]["headword"], "扱う")
        self.assertEqual(rows[0]["reading"], "あつかう")
        self.assertEqual(rows[0]["verb_pattern"], "他：～を")
        self.assertEqual(rows[0]["meaning_zh"], "处理")
        self.assertEqual(rows[0]["examples"][0]["text"], "この問題を扱う。")
        self.assertEqual(rows[1]["headword"], "表す")
        self.assertNotIn("出现次数", json.dumps(rows, ensure_ascii=False))

    def test_import_reuses_exact_item_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "n2vocab.sqlite"
            create_canonical_schema(db_path)
            seed_existing_item(db_path)
            payload = payload_with_550_entries()

            first = import_rows(db_path, payload)
            second = import_rows(db_path, payload)

            self.assertEqual(first["entries_seen"], 550)
            self.assertEqual(second["book_entries"], 550)
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            try:
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM book_entries WHERE book_code=?", (BOOK_CODE,)).fetchone()[0],
                    550,
                )
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM entries WHERE book_code=?", (BOOK_CODE,)).fetchone()[0],
                    550,
                )
                first_entry = conn.execute(
                    "SELECT item_id FROM book_entries WHERE book_code=? AND source_index=1",
                    (BOOK_CODE,),
                ).fetchone()
                self.assertEqual(first_entry["item_id"], 100)
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM item_examples WHERE item_id=100").fetchone()[0],
                    2,
                )
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM item_source_notes WHERE source_book_code=?",
                        (BOOK_CODE,),
                    ).fetchone()[0],
                    550,
                )
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM item_example_sources WHERE source_book_code=?",
                        (BOOK_CODE,),
                    ).fetchone()[0],
                    550,
                )
                self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(len(conn.execute("PRAGMA foreign_key_check").fetchall()), 0)
            finally:
                conn.close()


def payload_with_550_entries() -> dict:
    entries = []
    sections = ["动词", "名词", "形容词", "副词"]
    for index in range(1, 551):
        section = sections[min((index - 1) // 140, 3)]
        if index == 1:
            headword = "扱う"
            reading = "あつかう"
            meaning = "处理"
            text = "この問題を扱う。"
            translation = "处理这个问题。"
        else:
            headword = f"語{index}"
            reading = f"ご{index}"
            meaning = f"意思{index}"
            text = f"語{index}を使う。"
            translation = f"使用词{index}。"
        entries.append(
            {
                "source_index": index,
                "section": section,
                "headword": headword,
                "reading": reading,
                "verb_pattern": "他：～を" if section == "动词" else "",
                "meaning_zh": meaning,
                "examples": [{"text": text, "translation_zh": translation, "sense": meaning}],
                "notes": ["注意：fixture note"] if index == 1 else [],
            }
        )
    return {"entries": entries}


def create_canonical_schema(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT);
        INSERT INTO schema_migrations(version, name) VALUES
          (1, 'initial_schema'),
          (2, 'entry_example_metadata'),
          (3, 'entry_source_provenance'),
          (4, 'entry_example_category'),
          (6, 'entry_example_kind'),
          (7, 'vocabulary_items');
        CREATE TABLE books(code TEXT PRIMARY KEY, title TEXT NOT NULL, notes TEXT);
        CREATE TABLE units(
          book_code TEXT NOT NULL REFERENCES books(code) ON DELETE CASCADE,
          number INTEGER NOT NULL,
          header TEXT NOT NULL,
          title TEXT NOT NULL,
          PRIMARY KEY(book_code, number)
        );
        CREATE TABLE entries(
          entry_id INTEGER PRIMARY KEY,
          uuid TEXT NOT NULL UNIQUE,
          book_code TEXT NOT NULL,
          unit_number INTEGER NOT NULL,
          source_index INTEGER NOT NULL,
          position INTEGER NOT NULL,
          kanji TEXT NOT NULL,
          reading TEXT,
          headword_text TEXT NOT NULL,
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
        CREATE TABLE entry_examples(
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
        CREATE TABLE word_marks(
          entry_id INTEGER PRIMARY KEY REFERENCES entries(entry_id) ON DELETE CASCADE,
          known INTEGER NOT NULL DEFAULT 0,
          flagged INTEGER NOT NULL DEFAULT 0,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE vocabulary_items(
          item_id INTEGER PRIMARY KEY,
          uuid TEXT NOT NULL UNIQUE,
          kanji TEXT NOT NULL,
          reading TEXT,
          verb_pattern TEXT,
          meaning_en TEXT,
          meaning_zh TEXT,
          explanation_md TEXT,
          word_clip TEXT,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(kanji, reading)
        );
        CREATE TABLE book_entries(
          entry_id INTEGER PRIMARY KEY,
          item_id INTEGER NOT NULL REFERENCES vocabulary_items(item_id) ON DELETE CASCADE,
          uuid TEXT NOT NULL UNIQUE,
          book_code TEXT NOT NULL REFERENCES books(code) ON DELETE CASCADE,
          unit_number INTEGER NOT NULL,
          source_index INTEGER NOT NULL,
          position INTEGER NOT NULL,
          sentence TEXT,
          explanation_md TEXT,
          sentence_clip TEXT,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(book_code, source_index),
          FOREIGN KEY(book_code, unit_number) REFERENCES units(book_code, number)
        );
        CREATE TABLE item_examples(
          item_id INTEGER NOT NULL REFERENCES vocabulary_items(item_id) ON DELETE CASCADE,
          position INTEGER NOT NULL,
          kind TEXT NOT NULL DEFAULT 'example_sentence',
          text TEXT NOT NULL,
          reading TEXT,
          translation_en TEXT,
          translation_zh TEXT,
          explanation_md TEXT,
          audio_clip TEXT,
          category TEXT,
          PRIMARY KEY(item_id, position)
        );
        CREATE TABLE item_marks(
          item_id INTEGER PRIMARY KEY REFERENCES vocabulary_items(item_id) ON DELETE CASCADE,
          known INTEGER NOT NULL DEFAULT 0,
          flagged INTEGER NOT NULL DEFAULT 0,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE item_source_notes(
          item_id INTEGER NOT NULL REFERENCES vocabulary_items(item_id) ON DELETE CASCADE,
          source_book_code TEXT NOT NULL,
          source_entry_uuid TEXT NOT NULL,
          source_index INTEGER NOT NULL,
          source_reading TEXT,
          source_meaning_en TEXT,
          source_meaning_zh TEXT,
          source_explanation_md TEXT,
          source_sentence TEXT,
          source_translation_en TEXT,
          source_translation_zh TEXT,
          source_word_clip TEXT,
          source_sentence_clip TEXT,
          PRIMARY KEY(item_id, source_book_code, source_index)
        );
        CREATE TABLE item_example_sources(
          item_id INTEGER NOT NULL,
          position INTEGER NOT NULL,
          source_book_code TEXT NOT NULL,
          source_index INTEGER NOT NULL,
          PRIMARY KEY(item_id, position, source_book_code, source_index),
          FOREIGN KEY(item_id, position) REFERENCES item_examples(item_id, position) ON DELETE CASCADE,
          FOREIGN KEY(item_id, source_book_code, source_index)
            REFERENCES item_source_notes(item_id, source_book_code, source_index) ON DELETE CASCADE
        );
        CREATE TABLE vocabulary_migration_reports(
          kind TEXT NOT NULL,
          group_key TEXT NOT NULL,
          detail TEXT NOT NULL,
          row_count INTEGER NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY(kind, group_key)
        );
        """
    )
    conn.close()


def seed_existing_item(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO vocabulary_items(
          item_id, uuid, kanji, reading, verb_pattern, meaning_en, meaning_zh,
          explanation_md, word_clip
        )
        VALUES(100, 'existing-item', '扱う', 'あつかう', '他：～を', '', '处理', '', NULL)
        """
    )
    conn.execute(
        """
        INSERT INTO item_examples(
          item_id, position, kind, text, reading, translation_en,
          translation_zh, explanation_md, audio_clip, category
        )
        VALUES(100, 0, 'main_sentence', '既存の例文。', '', '', '既有例句。', '', NULL, NULL)
        """
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    unittest.main()
