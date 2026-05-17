"""
db.connect — shared SQLite access for the N2 vocabulary project.

`load_entries()` returns rows in the same shape as the old vocabulary.json
list-of-dicts, so existing builders only need to swap their data source.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "output" / "n2vocab.sqlite"


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def load_entries(book_code: str = "N2", db_path: Path | str | None = None) -> list[dict]:
    """
    Return entries shaped like the legacy vocabulary.json list-of-dicts:
      {index, unit:{number,header}, kanji, reading, headword_text, verb_pattern,
       meaning_en, meaning_zh, sentence, examples, word_clip, sentence_clip,
       explanation, uuid, book_code}

    `index` is the per-book source_index (1..N within the book). The DB's
    surrogate entry_id is also exposed as `entry_id` for callers that need it.
    """
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT e.entry_id, e.uuid, e.book_code, e.source_index,
                   e.unit_number, u.header AS unit_header,
                   e.kanji, e.reading, e.headword_text, e.verb_pattern,
                   e.meaning_en, e.meaning_zh, e.sentence, e.explanation_md,
                   e.word_clip, e.sentence_clip
              FROM entries e
              JOIN units u
                ON u.book_code = e.book_code AND u.number = e.unit_number
             WHERE e.book_code = ?
             ORDER BY e.unit_number, e.position, e.source_index
            """,
            (book_code,),
        ).fetchall()

        ex_rows = conn.execute(
            """
            SELECT x.entry_id, x.text
              FROM entry_examples x
              JOIN entries e ON e.entry_id = x.entry_id
             WHERE e.book_code = ?
             ORDER BY x.entry_id, x.position
            """,
            (book_code,),
        ).fetchall()
    finally:
        conn.close()

    examples_by_entry: dict[int, list[str]] = defaultdict(list)
    for r in ex_rows:
        examples_by_entry[r["entry_id"]].append(r["text"])

    out: list[dict] = []
    for r in rows:
        out.append({
            "index": r["source_index"],
            "entry_id": r["entry_id"],
            "uuid": r["uuid"],
            "book_code": r["book_code"],
            "unit": {"number": r["unit_number"], "header": r["unit_header"]},
            "kanji": r["kanji"] or "",
            "reading": r["reading"] or "",
            "headword_text": r["headword_text"] or "",
            "verb_pattern": r["verb_pattern"],
            "meaning_en": r["meaning_en"] or "",
            "meaning_zh": r["meaning_zh"] or "",
            "sentence": r["sentence"] or "",
            "examples": examples_by_entry.get(r["entry_id"], []),
            "explanation": r["explanation_md"] or "",
            "word_clip": r["word_clip"],
            "sentence_clip": r["sentence_clip"],
        })
    return out
