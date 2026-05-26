from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server import WordRepository


class WordRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.db_path = root / "n2vocab.sqlite"
        self.clips_dir = root / "clips"
        (self.clips_dir / "unit1_track02").mkdir(parents=True)
        (self.clips_dir / "unit1_track02" / "word001.mp3").write_bytes(b"word")
        (self.clips_dir / "unit1_track02" / "sentence001.mp3").write_bytes(b"sentence")

        conn = sqlite3.connect(self.db_path)
        try:
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
                CREATE TABLE entry_examples (
                  entry_id INTEGER NOT NULL REFERENCES entries(entry_id),
                  position INTEGER NOT NULL,
                  text TEXT NOT NULL,
                  translation_en TEXT,
                  translation_zh TEXT,
                  explanation_md TEXT,
                  audio_clip TEXT,
                  PRIMARY KEY(entry_id, position)
                );
                CREATE TABLE word_marks (
                  entry_id INTEGER PRIMARY KEY REFERENCES entries(entry_id),
                  known INTEGER NOT NULL DEFAULT 0 CHECK(known IN (0,1)),
                  flagged INTEGER NOT NULL DEFAULT 0 CHECK(flagged IN (0,1)),
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                INSERT INTO books(code, title) VALUES('N2', 'N2');
                INSERT INTO units(book_code, number, header, title)
                VALUES('N2', 1, 'Unit 01 名詞 A', '名詞 A');
                INSERT INTO entries(
                  entry_id, uuid, book_code, unit_number, source_index, position,
                  kanji, reading, headword_text, meaning_en, meaning_zh,
                  sentence, explanation_md, word_clip, sentence_clip
                )
                VALUES
                  (1, 'uuid-1', 'N2', 1, 1, 1, '人生', 'じんせい', '人生',
                   'life', '人生', '幸せな人生を送る。', 'explain one',
                   'clips/unit1_track02/word001.mp3', 'clips/unit1_track02/sentence001.mp3'),
                  (2, 'uuid-2', 'N2', 1, 2, 2, '男性', 'だんせい', '男性',
                   'man', '男性', '男性の友人。', NULL, NULL, NULL);
                INSERT INTO entry_examples(
                  entry_id, position, text, translation_en, translation_zh, explanation_md, audio_clip
                )
                VALUES
                  (1, 0, '幸せな人生を送る。', 'Live a happy life.', '度过幸福的人生。',
                   'main explanation', 'clips/unit1_track02/sentence001.mp3'),
                  (1, 1, '人生経験が豊富だ。', 'Has rich life experience.', '人生经验丰富。', NULL, NULL);
                INSERT INTO word_marks(entry_id, known, flagged)
                VALUES(1, 1, 0);
                """
            )
            conn.commit()
        finally:
            conn.close()

        self.repo = WordRepository(self.db_path, self.clips_dir, "N2")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_summary_and_units_include_mark_counts(self) -> None:
        self.assertEqual(
            self.repo.get_summary(),
            {"entries": 2, "units": 1, "known": 1, "flagged": 0, "unmarked": 1},
        )
        unit = self.repo.list_units()[0]
        self.assertEqual(unit["entry_count"], 2)
        self.assertEqual(unit["known"], 1)

    def test_entry_listing_search_and_state_filters(self) -> None:
        known = self.repo.list_entries(unit=1, state="known")["items"]
        self.assertEqual([row["entry_id"] for row in known], [1])

        unmarked = self.repo.list_entries(unit=1, state="unmarked")["items"]
        self.assertEqual([row["entry_id"] for row in unmarked], [2])

        searched = self.repo.list_entries(unit=1, search="happy")["items"]
        self.assertEqual([row["entry_id"] for row in searched], [1])

    def test_detail_includes_examples_and_audio_urls(self) -> None:
        entry = self.repo.get_entry(1)
        assert entry is not None
        self.assertEqual(len(entry["examples"]), 2)
        self.assertEqual(entry["word_audio_url"], "/audio/clips/unit1_track02/word001.mp3")
        self.assertEqual(entry["sentence_audio_url"], "/audio/clips/unit1_track02/sentence001.mp3")

    def test_mark_upsert_delete_and_unknown_entry(self) -> None:
        self.repo.set_mark(2, known=False, flagged=True)
        row = self.repo.get_entry(2)
        assert row is not None
        self.assertTrue(row["mark"]["flagged"])

        self.repo.set_mark(2, known=False, flagged=False)
        row = self.repo.get_entry(2)
        assert row is not None
        self.assertFalse(row["mark"]["known"])
        self.assertFalse(row["mark"]["flagged"])

        with self.assertRaises(KeyError):
            self.repo.set_mark(999, known=True, flagged=False)

    def test_audio_resolution_stays_inside_clips(self) -> None:
        valid = self.repo.resolve_audio_path("clips/unit1_track02/word001.mp3")
        self.assertIsNotNone(valid)
        self.assertIsNone(self.repo.resolve_audio_path("../output/n2vocab.sqlite"))
        self.assertIsNone(self.repo.resolve_audio_path("output/clips/unit1_track02/word001.mp3"))


if __name__ == "__main__":
    unittest.main()
