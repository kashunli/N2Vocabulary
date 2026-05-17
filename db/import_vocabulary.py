"""
db/import_vocabulary.py — One-shot import of vocabulary.json into SQLite.

Idempotent: re-running upserts books/units/entries and replaces examples for
each entry. UUIDs are preserved across re-imports — generated only the first
time a given (book_code, source_index) is seen.

Also folds in any existing output/word_marks.json once.

Usage:
    python db/import_vocabulary.py                       # imports as book N2
    python db/import_vocabulary.py --book N3 \
        --json other_book.json --title "N3 語彙トレーニング"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

from connect import DB_PATH, connect  # type: ignore[import-not-found]
from migrate import apply_all          # type: ignore[import-not-found]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JSON = PROJECT_ROOT / "vocabulary.json"
MARKS_JSON = PROJECT_ROOT / "output" / "word_marks.json"


def short_title(header: str) -> str:
    t = re.sub(r"^Unit\s+\d+\s+", "", header).strip()
    t = re.sub(r"\s*&\s*Column.*$", "", t).strip()
    return t or header


def import_book(
    *,
    book_code: str,
    book_title: str,
    json_path: Path,
    preserve_entry_id: bool,
    db_path: Path | None = None,
) -> None:
    if not json_path.exists():
        print(f"ERROR: {json_path} not found", file=sys.stderr)
        sys.exit(1)

    data = json.loads(json_path.read_text(encoding="utf-8"))
    print(f"loaded {len(data)} entries from {json_path.name}")

    conn = connect(db_path)
    try:
        conn.execute("BEGIN")

        # Book row
        conn.execute(
            "INSERT INTO books (code, title) VALUES (?, ?) "
            "ON CONFLICT(code) DO UPDATE SET title = excluded.title",
            (book_code, book_title),
        )

        # Units
        seen_units: dict[int, str] = {}
        for e in data:
            n = e["unit"]["number"]
            seen_units.setdefault(n, e["unit"]["header"])
        for number, header in seen_units.items():
            conn.execute(
                "INSERT INTO units (book_code, number, header, title) VALUES (?,?,?,?) "
                "ON CONFLICT(book_code, number) DO UPDATE SET "
                "header = excluded.header, title = excluded.title",
                (book_code, number, header, short_title(header)),
            )

        # Existing UUIDs (so re-imports don't churn them)
        existing_uuid: dict[tuple[str, int], str] = {}
        existing_entry_id: dict[tuple[str, int], int] = {}
        for r in conn.execute(
            "SELECT book_code, source_index, uuid, entry_id FROM entries WHERE book_code = ?",
            (book_code,),
        ):
            existing_uuid[(r["book_code"], r["source_index"])] = r["uuid"]
            existing_entry_id[(r["book_code"], r["source_index"])] = r["entry_id"]

        # Per-unit position counter
        pos_in_unit: dict[int, int] = {}

        for e in data:
            unit_n = e["unit"]["number"]
            pos_in_unit[unit_n] = pos_in_unit.get(unit_n, 0) + 1
            position = pos_in_unit[unit_n]

            source_index = int(e["index"])
            key = (book_code, source_index)
            row_uuid = existing_uuid.get(key) or str(uuid.uuid4())
            row_entry_id = (
                existing_entry_id.get(key)
                or (source_index if preserve_entry_id else None)
            )

            params = {
                "entry_id":      row_entry_id,        # may be None → auto
                "uuid":          row_uuid,
                "book_code":     book_code,
                "unit_number":   unit_n,
                "source_index":  source_index,
                "position":      position,
                "kanji":         e.get("kanji") or "",
                "reading":       e.get("reading") or None,
                "headword_text": e.get("headword_text") or e.get("kanji") or "",
                "verb_pattern":  e.get("verb_pattern"),
                "meaning_en":    e.get("meaning_en") or "",
                "meaning_zh":    e.get("meaning_zh") or "",
                "sentence":      e.get("sentence") or "",
                "explanation_md": e.get("explanation") or "",
                "word_clip":     e.get("word_clip"),
                "sentence_clip": e.get("sentence_clip"),
            }

            # UPSERT on the natural key (book_code, source_index)
            conn.execute(
                """
                INSERT INTO entries (
                  entry_id, uuid, book_code, unit_number, source_index, position,
                  kanji, reading, headword_text, verb_pattern,
                  meaning_en, meaning_zh, sentence, explanation_md,
                  word_clip, sentence_clip
                ) VALUES (
                  :entry_id, :uuid, :book_code, :unit_number, :source_index, :position,
                  :kanji, :reading, :headword_text, :verb_pattern,
                  :meaning_en, :meaning_zh, :sentence, :explanation_md,
                  :word_clip, :sentence_clip
                )
                ON CONFLICT(book_code, source_index) DO UPDATE SET
                  unit_number   = excluded.unit_number,
                  position      = excluded.position,
                  kanji         = excluded.kanji,
                  reading       = excluded.reading,
                  headword_text = excluded.headword_text,
                  verb_pattern  = excluded.verb_pattern,
                  meaning_en    = excluded.meaning_en,
                  meaning_zh    = excluded.meaning_zh,
                  sentence      = excluded.sentence,
                  explanation_md = excluded.explanation_md,
                  word_clip     = excluded.word_clip,
                  sentence_clip = excluded.sentence_clip
                """,
                params,
            )

            # Resolve the row's surrogate entry_id (auto-assigned for N3+).
            row_id = conn.execute(
                "SELECT entry_id FROM entries WHERE book_code = ? AND source_index = ?",
                (book_code, source_index),
            ).fetchone()["entry_id"]

            # Replace examples for this entry (cheap + simple). Position 0 is
            # reserved for the main sentence and carries sentence-specific
            # metadata; positions 1+ are the book's additional examples.
            conn.execute("DELETE FROM entry_examples WHERE entry_id = ?", (row_id,))
            if e.get("sentence"):
                conn.execute(
                    """
                    INSERT INTO entry_examples (
                      entry_id, position, text, translation_en, translation_zh,
                      explanation_md, audio_clip
                    ) VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        row_id,
                        0,
                        e.get("sentence") or "",
                        e.get("sentence_translation_en") or e.get("translation_en") or "",
                        e.get("sentence_translation_zh") or e.get("translation_zh") or "",
                        e.get("explanation") or "",
                        e.get("sentence_clip"),
                    ),
                )
            for i, ex_text in enumerate(e.get("examples") or [], start=1):
                if isinstance(ex_text, dict):
                    text = ex_text.get("text") or ""
                    translation_en = ex_text.get("translation_en") or ""
                    translation_zh = ex_text.get("translation_zh") or ""
                    explanation_md = ex_text.get("explanation") or ex_text.get("explanation_md") or ""
                    audio_clip = ex_text.get("audio_clip")
                else:
                    text = str(ex_text)
                    translation_en = ""
                    translation_zh = ""
                    explanation_md = ""
                    audio_clip = None
                conn.execute(
                    """
                    INSERT INTO entry_examples (
                      entry_id, position, text, translation_en, translation_zh,
                      explanation_md, audio_clip
                    ) VALUES (?,?,?,?,?,?,?)
                    """,
                    (row_id, i, text, translation_en, translation_zh, explanation_md, audio_clip),
                )

        conn.execute("COMMIT")
        print(f"imported {len(data)} entries into book {book_code!r}.")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def import_marks_json(db_path: Path | None = None) -> None:
    if not MARKS_JSON.exists():
        print(f"  no {MARKS_JSON.name} to fold in.")
        return
    try:
        payload = json.loads(MARKS_JSON.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"WARN: cannot read {MARKS_JSON}: {e}")
        return
    marks = payload.get("marks") or {}
    if not marks:
        print(f"  {MARKS_JSON.name} present but empty; skipping.")
        return

    conn = connect(db_path)
    try:
        conn.execute("BEGIN")
        n = 0
        for entry_id_str, m in marks.items():
            try:
                entry_id = int(entry_id_str)
            except ValueError:
                continue
            row = conn.execute(
                "SELECT 1 FROM entries WHERE entry_id = ?", (entry_id,)
            ).fetchone()
            if not row:
                continue
            conn.execute(
                """
                INSERT INTO word_marks (entry_id, known, flagged, updated_at)
                VALUES (?, ?, ?, COALESCE(?, strftime('%Y-%m-%dT%H:%M:%fZ','now')))
                ON CONFLICT(entry_id) DO UPDATE SET
                  known      = excluded.known,
                  flagged    = excluded.flagged,
                  updated_at = excluded.updated_at
                """,
                (entry_id, 1 if m.get("known") else 0, 1 if m.get("flagged") else 0, m.get("updated_at")),
            )
            n += 1
        conn.execute("COMMIT")
        print(f"  imported {n} mark rows from {MARKS_JSON.name}.")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default="N2", help="book code (default: N2)")
    ap.add_argument("--title", default="N2 語彙トレーニング", help="book title")
    ap.add_argument("--json", default=str(DEFAULT_JSON), help="source JSON path")
    ap.add_argument("--db", default=None, help="override DB path")
    ap.add_argument("--auto-entry-id", action="store_true",
                    help="let SQLite auto-assign entry_id (default for non-N2 books)")
    args = ap.parse_args()

    print(f"db: {Path(args.db).resolve() if args.db else DB_PATH}")
    apply_all(args.db)

    # Default policy: preserve legacy 1..N entry_ids for N2; auto for others.
    preserve = (args.book.upper() == "N2") and not args.auto_entry_id

    import_book(
        book_code=args.book.upper(),
        book_title=args.title,
        json_path=Path(args.json),
        preserve_entry_id=preserve,
        db_path=args.db,
    )

    if args.book.upper() == "N2":
        import_marks_json(args.db)


if __name__ == "__main__":
    main()
