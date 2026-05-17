#!/usr/bin/env python3
"""
Repair OCR/parser rows where the leading kana `か` was stored as verb_pattern.

The HTML word/card renderers trust normalized data:
  - `reading` should contain the complete furigana/readout.
  - `verb_pattern` is reserved for real usage markers such as ガ/ヲ/スル.

Some older imported rows instead have values like:
  reading = "んかく", verb_pattern = "か"  # should be かんかく, no pattern

This script fixes the canonical backup JSON and the live SQLite rows without
re-importing the whole database, so sentence translations and marks already in
SQLite are preserved.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VOCAB_JSON = PROJECT_ROOT / "vocabulary.json"
DB_PATH = PROJECT_ROOT / "output" / "n2vocab.sqlite"


def repaired_reading(reading: str | None) -> str | None:
    if not reading:
        return reading
    if reading.startswith("か"):
        return reading
    return "か" + reading


def repair_vocabulary_json(path: Path, *, dry_run: bool) -> tuple[int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    changed_rows = 0
    restored_readings = 0

    for entry in data:
        if entry.get("verb_pattern") != "か":
            continue
        old_reading = entry.get("reading")
        new_reading = repaired_reading(old_reading)
        if new_reading != old_reading:
            entry["reading"] = new_reading
            restored_readings += 1
        entry["verb_pattern"] = None
        changed_rows += 1

    if changed_rows and not dry_run:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return changed_rows, restored_readings


def repair_sqlite(path: Path, *, dry_run: bool) -> tuple[int, int]:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT entry_id, source_index, reading, verb_pattern
              FROM entries
             WHERE book_code = 'N2' AND verb_pattern = 'か'
             ORDER BY source_index
            """
        ).fetchall()

        changed_rows = 0
        restored_readings = 0
        if rows and not dry_run:
            conn.execute("BEGIN")
        for row in rows:
            old_reading = row["reading"]
            new_reading = repaired_reading(old_reading)
            if new_reading != old_reading:
                restored_readings += 1
            changed_rows += 1
            if not dry_run:
                conn.execute(
                    """
                    UPDATE entries
                       SET reading = ?, verb_pattern = NULL
                     WHERE entry_id = ?
                    """,
                    (new_reading, row["entry_id"]),
                )
        if rows and not dry_run:
            conn.execute("COMMIT")
        return changed_rows, restored_readings
    except Exception:
        if not dry_run:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    vocab_changed, vocab_restored = repair_vocabulary_json(VOCAB_JSON, dry_run=args.dry_run)
    db_changed, db_restored = repair_sqlite(DB_PATH, dry_run=args.dry_run)

    mode = "would repair" if args.dry_run else "repaired"
    print(
        f"{mode} vocabulary.json: {vocab_changed} rows, "
        f"{vocab_restored} readings restored"
    )
    print(
        f"{mode} SQLite entries: {db_changed} rows, "
        f"{db_restored} readings restored"
    )


if __name__ == "__main__":
    main()
