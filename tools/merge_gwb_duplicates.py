"""Merge exact GreenWordBook duplicates into their existing N2/N3 entries.

The default command is a read-only dry run. ``--apply`` creates a timestamped
backup, performs the merge in one transaction, validates the database, and
writes a structured summary for later agents to audit.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "wordService" / "data" / "n2vocab.sqlite"
DEFAULT_SUMMARY = PROJECT_ROOT / "output" / "gwb_duplicate_merge_summary.json"
SOURCE_BOOK = "GWB_N2"
DESTINATION_BOOKS = ("N2", "N3")
NANTOKA_TARGET_ENTRY_ID = 1099


@dataclass(frozen=True)
class Mapping:
    source_entry_id: int
    source_index: int
    destination_entry_id: int
    destination_book: str
    kanji: str


def connect(db_path: Path, *, read_only: bool = False) -> sqlite3.Connection:
    if read_only:
        conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_provenance_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS entry_source_notes (
          entry_id INTEGER NOT NULL REFERENCES entries(entry_id) ON DELETE CASCADE,
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
          PRIMARY KEY (entry_id, source_book_code, source_index)
        );
        CREATE INDEX IF NOT EXISTS idx_entry_source_notes_source
          ON entry_source_notes(source_book_code, source_index);
        CREATE TABLE IF NOT EXISTS entry_example_sources (
          entry_id INTEGER NOT NULL,
          position INTEGER NOT NULL,
          source_book_code TEXT NOT NULL,
          source_index INTEGER NOT NULL,
          PRIMARY KEY (entry_id, position, source_book_code, source_index),
          FOREIGN KEY (entry_id, position)
            REFERENCES entry_examples(entry_id, position) ON DELETE CASCADE,
          FOREIGN KEY (entry_id, source_book_code, source_index)
            REFERENCES entry_source_notes(entry_id, source_book_code, source_index)
            ON DELETE CASCADE
        );
        """
    )


def build_mappings(conn: sqlite3.Connection) -> list[Mapping]:
    source_rows = conn.execute(
        """
        SELECT entry_id, source_index, kanji
        FROM entries g
        WHERE g.book_code = ?
          AND EXISTS (
            SELECT 1 FROM entries d
            WHERE d.book_code IN ('N2', 'N3') AND d.kanji = g.kanji
          )
        ORDER BY source_index, entry_id
        """,
        (SOURCE_BOOK,),
    ).fetchall()
    mappings: list[Mapping] = []
    for source in source_rows:
        if source["kanji"] == "何とか":
            targets = conn.execute(
                "SELECT entry_id, book_code FROM entries WHERE entry_id = ? AND book_code = 'N2' AND kanji = ?",
                (NANTOKA_TARGET_ENTRY_ID, source["kanji"]),
            ).fetchall()
        else:
            targets = conn.execute(
                """
                SELECT entry_id, book_code
                FROM entries
                WHERE book_code IN ('N2', 'N3') AND kanji = ?
                ORDER BY CASE book_code WHEN 'N2' THEN 0 ELSE 1 END, entry_id
                """,
                (source["kanji"],),
            ).fetchall()
        if len(targets) != 1:
            raise ValueError(
                f"Expected one destination for GWB #{source['source_index']} "
                f"{source['kanji']!r}; found {len(targets)}"
            )
        target = targets[0]
        mappings.append(
            Mapping(
                source_entry_id=source["entry_id"],
                source_index=source["source_index"],
                destination_entry_id=target["entry_id"],
                destination_book=target["book_code"],
                kanji=source["kanji"],
            )
        )
    return mappings


def _source_note(conn: sqlite3.Connection, mapping: Mapping) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT g.uuid, g.reading, g.meaning_en, g.meaning_zh,
               g.explanation_md, g.sentence, g.word_clip, g.sentence_clip,
               x.text AS example_text, x.translation_en, x.translation_zh,
               x.explanation_md AS example_explanation, x.audio_clip
        FROM entries g
        LEFT JOIN entry_examples x
          ON x.entry_id = g.entry_id
         AND (x.kind = 'main_sentence' OR x.position = 0)
        WHERE g.entry_id = ?
        ORDER BY CASE WHEN x.kind = 'main_sentence' THEN 0 ELSE 1 END,
                 x.position
        LIMIT 1
        """,
        (mapping.source_entry_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Missing source entry {mapping.source_entry_id}")
    return row


def _insert_source_note(conn: sqlite3.Connection, mapping: Mapping, row: sqlite3.Row) -> None:
    conn.execute(
        """
        INSERT INTO entry_source_notes(
          entry_id, source_book_code, source_entry_uuid, source_index,
          source_reading, source_meaning_en, source_meaning_zh,
          source_explanation_md, source_sentence, source_translation_en,
          source_translation_zh, source_word_clip, source_sentence_clip
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(entry_id, source_book_code, source_index) DO UPDATE SET
          source_entry_uuid = excluded.source_entry_uuid,
          source_reading = excluded.source_reading,
          source_meaning_en = excluded.source_meaning_en,
          source_meaning_zh = excluded.source_meaning_zh,
          source_explanation_md = excluded.source_explanation_md,
          source_sentence = excluded.source_sentence,
          source_translation_en = excluded.source_translation_en,
          source_translation_zh = excluded.source_translation_zh,
          source_word_clip = excluded.source_word_clip,
          source_sentence_clip = excluded.source_sentence_clip
        """,
        (
            mapping.destination_entry_id,
            SOURCE_BOOK,
            row["uuid"],
            mapping.source_index,
            row["reading"],
            row["meaning_en"],
            row["meaning_zh"],
            row["explanation_md"],
            row["example_text"] or row["sentence"],
            row["translation_en"],
            row["translation_zh"],
            row["word_clip"],
            row["audio_clip"] or row["sentence_clip"],
        ),
    )


def _fill_blank_destination_fields(
    conn: sqlite3.Connection, mapping: Mapping, row: sqlite3.Row
) -> None:
    conn.execute(
        """
        UPDATE entries
        SET reading = CASE WHEN TRIM(COALESCE(reading, '')) = '' THEN ? ELSE reading END,
            meaning_en = CASE WHEN TRIM(COALESCE(meaning_en, '')) = '' THEN ? ELSE meaning_en END,
            word_clip = CASE WHEN TRIM(COALESCE(word_clip, '')) = '' THEN ? ELSE word_clip END
        WHERE entry_id = ?
        """,
        (row["reading"], row["meaning_en"], row["word_clip"], mapping.destination_entry_id),
    )


def _merge_mark(conn: sqlite3.Connection, mapping: Mapping) -> None:
    mark = conn.execute(
        "SELECT known, flagged, updated_at FROM word_marks WHERE entry_id = ?",
        (mapping.source_entry_id,),
    ).fetchone()
    if mark is None:
        return
    conn.execute(
        """
        INSERT INTO word_marks(entry_id, known, flagged, updated_at)
        VALUES(?, ?, ?, ?)
        ON CONFLICT(entry_id) DO UPDATE SET
          known = MAX(word_marks.known, excluded.known),
          flagged = MAX(word_marks.flagged, excluded.flagged),
          updated_at = MAX(word_marks.updated_at, excluded.updated_at)
        """,
        (mapping.destination_entry_id, mark["known"], mark["flagged"], mark["updated_at"]),
    )


def _merge_example(
    conn: sqlite3.Connection, mapping: Mapping, row: sqlite3.Row
) -> tuple[bool, bool]:
    text = (row["example_text"] or row["sentence"] or "").strip()
    if not text:
        return False, False
    existing = conn.execute(
        "SELECT position FROM entry_examples WHERE entry_id = ? AND TRIM(text) = ? ORDER BY position LIMIT 1",
        (mapping.destination_entry_id, text),
    ).fetchone()
    deduplicated = existing is not None
    if existing is None:
        position = conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM entry_examples WHERE entry_id = ?",
            (mapping.destination_entry_id,),
        ).fetchone()[0]
        conn.execute(
            """
            INSERT INTO entry_examples(
              entry_id, position, text, translation_en, translation_zh,
              explanation_md, audio_clip, kind
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mapping.destination_entry_id,
                position,
                text,
                row["translation_en"],
                row["translation_zh"],
                row["example_explanation"],
                row["audio_clip"] or row["sentence_clip"],
                "example_sentence",
            ),
        )
    else:
        position = existing["position"]
        conn.execute(
            """
            UPDATE entry_examples
            SET translation_en = CASE WHEN TRIM(COALESCE(translation_en, '')) = '' THEN ? ELSE translation_en END,
                translation_zh = CASE WHEN TRIM(COALESCE(translation_zh, '')) = '' THEN ? ELSE translation_zh END,
                explanation_md = CASE WHEN TRIM(COALESCE(explanation_md, '')) = '' THEN ? ELSE explanation_md END,
                audio_clip = CASE WHEN TRIM(COALESCE(audio_clip, '')) = '' THEN ? ELSE audio_clip END
            WHERE entry_id = ? AND position = ?
            """,
            (
                row["translation_en"],
                row["translation_zh"],
                row["example_explanation"],
                row["audio_clip"] or row["sentence_clip"],
                mapping.destination_entry_id,
                position,
            ),
        )
    conn.execute(
        """
        INSERT OR IGNORE INTO entry_example_sources(
          entry_id, position, source_book_code, source_index
        ) VALUES(?, ?, ?, ?)
        """,
        (mapping.destination_entry_id, position, SOURCE_BOOK, mapping.source_index),
    )
    return True, deduplicated


def restore_provenance_examples(
    conn: sqlite3.Connection, destination_book: str | None = None
) -> dict[str, int]:
    """Restore GWB examples after a destination importer replaces examples."""
    ensure_provenance_schema(conn)
    params: tuple[Any, ...] = ()
    clause = ""
    if destination_book:
        clause = "AND e.book_code = ?"
        params = (destination_book,)
    rows = conn.execute(
        f"""
        SELECT n.*, e.book_code
        FROM entry_source_notes n
        JOIN entries e ON e.entry_id = n.entry_id
        WHERE n.source_book_code = '{SOURCE_BOOK}' {clause}
        ORDER BY n.entry_id, n.source_index
        """,
        params,
    ).fetchall()
    appended = deduplicated = 0
    for row in rows:
        mapping = Mapping(
            source_entry_id=-1,
            source_index=row["source_index"],
            destination_entry_id=row["entry_id"],
            destination_book=row["book_code"],
            kanji="",
        )
        proxy = {
            "example_text": row["source_sentence"],
            "sentence": row["source_sentence"],
            "translation_en": row["source_translation_en"],
            "translation_zh": row["source_translation_zh"],
            "example_explanation": "",
            "audio_clip": row["source_sentence_clip"],
            "sentence_clip": row["source_sentence_clip"],
        }
        had_example, was_duplicate = _merge_example(conn, mapping, proxy)  # type: ignore[arg-type]
        appended += int(had_example and not was_duplicate)
        deduplicated += int(was_duplicate)
    return {"source_notes": len(rows), "examples_appended": appended, "examples_deduplicated": deduplicated}


def inspect(conn: sqlite3.Connection) -> dict[str, Any]:
    mappings = build_mappings(conn)
    by_book = {book: sum(m.destination_book == book for m in mappings) for book in DESTINATION_BOOKS}
    source_examples = 0
    duplicate_examples = 0
    # Include earlier GWB rows in the preview's deduplication state. Without
    # this, two source rows carrying the same sentence would both look new even
    # though apply correctly stores one example with two provenance links.
    seen_examples: set[tuple[int, str]] = set()
    for mapping in mappings:
        row = _source_note(conn, mapping)
        text = (row["example_text"] or row["sentence"] or "").strip()
        if not text:
            continue
        source_examples += 1
        key = (mapping.destination_entry_id, text)
        already_present = key in seen_examples or (
            conn.execute(
                "SELECT 1 FROM entry_examples WHERE entry_id = ? AND TRIM(text) = ? LIMIT 1",
                (mapping.destination_entry_id, text),
            ).fetchone()
            is not None
        )
        duplicate_examples += int(already_present)
        seen_examples.add(key)
    return {
        "mode": "dry-run",
        "source_book": SOURCE_BOOK,
        "matched_rows": len(mappings),
        "matched_headwords": len({m.kanji for m in mappings}),
        "destination_rows": by_book,
        "source_examples": source_examples,
        "examples_to_append": source_examples - duplicate_examples,
        "examples_to_deduplicate": duplicate_examples,
        "gwb_rows_before": conn.execute(
            "SELECT COUNT(*) FROM entries WHERE book_code = ?", (SOURCE_BOOK,)
        ).fetchone()[0],
    }


def apply_merge(db_path: Path) -> dict[str, Any]:
    with closing(connect(db_path, read_only=True)) as read_conn:
        before = inspect(read_conn)
    if before["matched_rows"] == 0:
        return {**before, "mode": "apply", "changed": False, "backup": None}
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = db_path.with_name(f"{db_path.name}.backup_before_gwb_duplicate_merge_{timestamp}")
    shutil.copy2(db_path, backup)
    conn = connect(db_path)
    appended = deduplicated = 0
    try:
        conn.execute("BEGIN IMMEDIATE")
        ensure_provenance_schema(conn)
        mappings = build_mappings(conn)
        for mapping in mappings:
            row = _source_note(conn, mapping)
            _insert_source_note(conn, mapping, row)
            _fill_blank_destination_fields(conn, mapping, row)
            _merge_mark(conn, mapping)
            had_example, was_duplicate = _merge_example(conn, mapping, row)
            appended += int(had_example and not was_duplicate)
            deduplicated += int(was_duplicate)
        conn.executemany(
            "DELETE FROM entries WHERE entry_id = ?",
            [(mapping.source_entry_id,) for mapping in mappings],
        )
        remaining_overlap = conn.execute(
            """
            SELECT COUNT(*) FROM entries g
            WHERE g.book_code = ? AND EXISTS(
              SELECT 1 FROM entries d
              WHERE d.book_code IN ('N2', 'N3') AND d.kanji = g.kanji
            )
            """,
            (SOURCE_BOOK,),
        ).fetchone()[0]
        foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if remaining_overlap or foreign_keys or integrity != "ok":
            raise RuntimeError(
                "Validation failed: "
                f"remaining_overlap={remaining_overlap}, "
                f"foreign_keys={len(foreign_keys)}, integrity={integrity}"
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        conn.close()
        raise
    finally:
        if conn:
            conn.close()
    with closing(connect(db_path, read_only=True)) as check:
        integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity check failed after commit: {integrity}")
        remaining = check.execute(
            "SELECT COUNT(*) FROM entries WHERE book_code = ?", (SOURCE_BOOK,)
        ).fetchone()[0]
        notes = check.execute(
            "SELECT COUNT(*) FROM entry_source_notes WHERE source_book_code = ?", (SOURCE_BOOK,)
        ).fetchone()[0]
    return {
        **before,
        "mode": "apply",
        "changed": True,
        "backup": str(backup),
        "source_notes_preserved": notes,
        "examples_appended": appended,
        "examples_deduplicated": deduplicated,
        "gwb_rows_after": remaining,
        "integrity_check": integrity,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB), help="wordService SQLite database")
    parser.add_argument("--apply", action="store_true", help="backup and apply the merge")
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY), help="apply summary JSON")
    args = parser.parse_args()
    db_path = Path(args.db)
    if args.apply:
        summary = apply_merge(db_path)
        summary_path = Path(args.summary)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        with closing(connect(db_path, read_only=True)) as conn:
            summary = inspect(conn)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
