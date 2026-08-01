"""
db.connect — shared SQLite access for the N2 vocabulary project.

`load_entries()` returns rows in the same shape as the old vocabulary.json
list-of-dicts, so existing builders only need to swap their data source.
"""

from __future__ import annotations

import sqlite3
from urllib.parse import quote
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "wordService" / "data" / "n2vocab.sqlite"


def connect(
    db_path: Path | str | None = None,
    *,
    read_only: bool = False,
    immutable: bool = False,
) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DB_PATH
    if read_only:
        uri = f"file:{quote(str(path.resolve()))}?mode=ro"
        if immutable:
            # The project often lives on a Windows-mounted drive. Immutable
            # reads avoid fragile WAL sidecar access while still reading the
            # checked SQLite file directly.
            uri += "&immutable=1"
        conn = sqlite3.connect(uri, uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def load_entries(book_code: str = "N2", db_path: Path | str | None = None) -> list[dict]:
    """
    Return entries shaped like the legacy vocabulary.json list-of-dicts:
      {index, unit:{number,header}, kanji, reading, headword_text, verb_pattern,
       meaning_en, meaning_zh, sentence, examples, word_clip, sentence_clip,
       explanation, uuid, book_code}

    The normalized source for the main example sentence is
    entry_examples.kind identifies the role of each row. Older
    entries.sentence / sentence_clip / explanation_md fields are retained as
    fallback compatibility data.

    `index` is the per-book source_index (1..N within the book). The DB's
    surrogate entry_id is also exposed as `entry_id` for callers that need it.
    """
    conn = connect(db_path, read_only=True, immutable=True)
    try:
        canonical = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='book_entries'"
        ).fetchone()
        if canonical:
            rows = conn.execute(
                """
                SELECT be.entry_id, be.item_id, be.uuid, be.book_code, be.source_index,
                       be.unit_number, u.header AS unit_header,
                       v.kanji, v.reading, v.kanji AS headword_text,
                       COALESCE(NULLIF(be.verb_pattern, ''), v.verb_pattern) AS verb_pattern,
                       COALESCE(NULLIF(be.meaning_en, ''), v.meaning_en) AS meaning_en,
                       COALESCE(NULLIF(be.meaning_zh, ''), v.meaning_zh) AS meaning_zh,
                       be.sentence,
                       COALESCE(be.explanation_md, v.explanation_md) AS explanation_md,
                       COALESCE(be.word_clip, v.word_clip) AS word_clip,
                       be.sentence_clip
                  FROM book_entries be
                  JOIN vocabulary_items v ON v.item_id = be.item_id
                  JOIN units u
                    ON u.book_code = be.book_code AND u.number = be.unit_number
                 WHERE be.book_code = ?
                 ORDER BY be.unit_number, be.position, be.source_index
                """,
                (book_code,),
            ).fetchall()

            ex_rows = conn.execute(
                """
                SELECT be.entry_id, x.position, x.text, x.translation_en,
                       x.translation_zh, x.explanation_md, x.audio_clip,
                       x.category, x.reading, x.kind
                  FROM item_examples x
                  JOIN book_entries be ON be.item_id = x.item_id
                 WHERE be.book_code = ?
                 ORDER BY be.entry_id, x.position
                """,
                (book_code,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT e.entry_id, e.entry_id AS item_id, e.uuid, e.book_code, e.source_index,
                       e.unit_number, u.header AS unit_header,
                       e.kanji, e.reading, e.kanji AS headword_text, e.verb_pattern,
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
                SELECT x.entry_id, x.position, x.text, x.translation_en,
                       x.translation_zh, x.explanation_md, x.audio_clip,
                       x.category, x.reading, x.kind
                  FROM entry_examples x
                  JOIN entries e ON e.entry_id = x.entry_id
                 WHERE e.book_code = ?
                 ORDER BY x.entry_id, x.position
                """,
                (book_code,),
            ).fetchall()
    finally:
        conn.close()

    examples_by_entry: dict[int, list[dict]] = defaultdict(list)
    for r in ex_rows:
        examples_by_entry[r["entry_id"]].append({
            "position": r["position"],
            "text": r["text"] or "",
            "translation_en": r["translation_en"] or "",
            "translation_zh": r["translation_zh"] or "",
            "explanation": r["explanation_md"] or "",
            "audio_clip": r["audio_clip"],
            "category": r["category"] or "",
            "reading": r["reading"] or "",
            "kind": r["kind"] or "example_sentence",
        })

    out: list[dict] = []
    for r in rows:
        example_items = examples_by_entry.get(r["entry_id"], [])
        main_example = next(
            (x for x in example_items if r["sentence"] and x["text"].strip() == r["sentence"].strip()),
            None,
        ) or next(
            (x for x in example_items if x["kind"] == "main_sentence" or x["position"] == 0),
            None,
        )
        extra_examples = [x for x in example_items if x is not main_example]
        if main_example is not None:
            # Examples are shared by vocabulary identity, but the first example
            # is book-specific. Present the current book's sentence first and
            # attach its book-specific audio without rewriting another book's
            # canonical example row.
            main_example = dict(main_example)
            main_example["kind"] = "main_sentence"
            main_example["audio_clip"] = r["sentence_clip"] or main_example.get("audio_clip")
            example_items = [main_example, *extra_examples]
        sentence = r["sentence"] or (main_example or {}).get("text") or ""
        sentence_clip = r["sentence_clip"] or (main_example or {}).get("audio_clip")
        explanation = (main_example or {}).get("explanation") or r["explanation_md"] or ""
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
            "sentence": sentence,
            "sentence_translation_en": (main_example or {}).get("translation_en", ""),
            "sentence_translation_zh": (main_example or {}).get("translation_zh", ""),
            "examples": [x["text"] for x in extra_examples],
            "example_items": example_items,
            "examples_detailed": extra_examples,
            "explanation": explanation,
            "word_clip": r["word_clip"],
            "sentence_clip": sentence_clip,
        })
    return out
