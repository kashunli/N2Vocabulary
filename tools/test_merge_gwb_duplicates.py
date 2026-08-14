from __future__ import annotations

import hashlib
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from merge_gwb_duplicates import apply_merge, connect, inspect, restore_provenance_examples


class MergeGwbDuplicatesTests(unittest.TestCase):
    def test_dry_run_is_read_only_and_routes_nantoka(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.sqlite"
            create_fixture(db_path)
            before = hashlib.sha256(db_path.read_bytes()).hexdigest()
            with closing(connect(db_path, read_only=True)) as conn:
                summary = inspect(conn)
            after = hashlib.sha256(db_path.read_bytes()).hexdigest()
            self.assertEqual(before, after)
            self.assertEqual(summary["matched_rows"], 4)
            self.assertEqual(summary["matched_headwords"], 3)
            self.assertEqual(summary["examples_to_append"], 3)
            self.assertEqual(summary["examples_to_deduplicate"], 1)

    def test_apply_preserves_provenance_progress_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.sqlite"
            create_fixture(db_path)
            summary = apply_merge(db_path)
            self.assertTrue(summary["changed"])
            self.assertEqual(summary["source_notes_preserved"], 4)
            self.assertEqual(summary["examples_appended"], 3)
            self.assertEqual(summary["examples_deduplicated"], 1)

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            try:
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM entries WHERE book_code='GWB_N2'").fetchone()[0],
                    1,
                )
                # The GWB sentence belongs to the manage-to sense, entry 1099.
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM entry_source_notes WHERE entry_id=1099 AND source_index=3"
                    ).fetchone()[0],
                    1,
                )
                mark = conn.execute(
                    "SELECT known,flagged FROM word_marks WHERE entry_id=20"
                ).fetchone()
                self.assertEqual((mark["known"], mark["flagged"]), (1, 1))
                conn.execute("DELETE FROM entry_examples WHERE entry_id=20 AND position>0")
                restored = restore_provenance_examples(conn, "N2")
                conn.commit()
                self.assertGreaterEqual(restored["examples_appended"], 1)
            finally:
                conn.close()

            second = apply_merge(db_path)
            self.assertFalse(second["changed"])
            self.assertEqual(second["matched_rows"], 0)


def create_fixture(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        PRAGMA foreign_keys=ON;
        CREATE TABLE books(code TEXT PRIMARY KEY,title TEXT NOT NULL,notes TEXT);
        CREATE TABLE units(book_code TEXT NOT NULL,number INTEGER NOT NULL,header TEXT NOT NULL,title TEXT NOT NULL,PRIMARY KEY(book_code,number));
        CREATE TABLE entries(
          entry_id INTEGER PRIMARY KEY,uuid TEXT NOT NULL UNIQUE,book_code TEXT NOT NULL,
          unit_number INTEGER NOT NULL,source_index INTEGER NOT NULL,position INTEGER NOT NULL,
          kanji TEXT NOT NULL,reading TEXT,verb_pattern TEXT,meaning_en TEXT,meaning_zh TEXT,
          sentence TEXT,explanation_md TEXT,word_clip TEXT,sentence_clip TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(book_code,source_index)
        );
        CREATE TABLE entry_examples(
          entry_id INTEGER NOT NULL REFERENCES entries(entry_id) ON DELETE CASCADE,
          position INTEGER NOT NULL,kind TEXT NOT NULL DEFAULT 'example_sentence',
          text TEXT NOT NULL,translation_en TEXT,translation_zh TEXT,
          explanation_md TEXT,audio_clip TEXT,PRIMARY KEY(entry_id,position)
        );
        CREATE TABLE word_marks(
          entry_id INTEGER PRIMARY KEY REFERENCES entries(entry_id) ON DELETE CASCADE,
          known INTEGER NOT NULL DEFAULT 0,flagged INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL
        );
        INSERT INTO books(code,title) VALUES('N2','N2'),('N3','N3'),('GWB_N2','GWB');
        INSERT INTO units(book_code,number,header,title) VALUES
          ('N2',1,'N2','N2'),('N3',1,'N3','N3'),('GWB_N2',1,'GWB','GWB');
        INSERT INTO entries(entry_id,uuid,book_code,unit_number,source_index,position,kanji,reading,meaning_en,meaning_zh,sentence,explanation_md) VALUES
          (20,'n2-a','N2',1,20,1,'共有','きょうゆう','share','共享','既存文。','existing'),
          (1095,'n2-b','N2',1,1095,2,'何とか','なんとか','somehow','设法','広い意味。','broad'),
          (1099,'n2-c','N2',1,1099,3,'何とか','なんとか','manage','总算','合格できた。','manage'),
          (30,'n3-a','N3',1,30,1,'別語','べつご','other','别词','N3文。','n3'),
          (100,'g-1','GWB_N2',1,1,1,'共有','きょうゆう','','共同','GWB文一。','note one'),
          (101,'g-2','GWB_N2',1,2,2,'共有','きょうゆう','','共享','既存文。','note two'),
          (102,'g-3','GWB_N2',1,3,3,'何とか','なんとか','','想办法','何とか仕上げる。','note three'),
          (103,'g-4','GWB_N2',1,4,4,'別語','べつご','','另一词','GWB N3文。','note four'),
          (104,'g-5','GWB_N2',1,5,5,'独自','どくじ','','独有','独自文。','unmatched');
        INSERT INTO entry_examples(entry_id,position,text,translation_zh,explanation_md) VALUES
          (20,0,'既存文。','现有句','existing sentence'),
          (1095,0,'広い意味。','广义','broad'),
          (1099,0,'合格できた。','通过了','manage'),
          (30,0,'N3文。','N3句','n3'),
          (100,0,'GWB文一。','GWB句一',''),
          (101,0,'既存文。','重复句',''),
          (102,0,'何とか仕上げる。','想办法完成',''),
          (103,0,'GWB N3文。','GWB N3句',''),
          (104,0,'独自文。','独有句','');
        INSERT INTO word_marks(entry_id,known,flagged,updated_at) VALUES
          (20,1,0,'2026-01-01'),(100,0,1,'2026-02-01');
        """
    )
    conn.close()


if __name__ == "__main__":
    unittest.main()
