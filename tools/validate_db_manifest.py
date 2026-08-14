"""Validate the canonical wordService SQLite manifest.

The checks here are intentionally read-only and report-oriented. They verify
the schema role columns, SQLite health, example-kind distribution, and the
remaining compatibility mismatch between entries.sentence and the main example.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "wordService" / "data" / "n2vocab.sqlite"


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the wordService DB manifest")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    conn = connect_readonly(args.db)
    try:
        print(f"db: {args.db}")
        print(f"integrity_check: {conn.execute('PRAGMA integrity_check').fetchone()[0]}")

        fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
        print(f"foreign_key_check_rows: {len(fk_rows)}")
        for row in fk_rows[:20]:
            print(f"  foreign_key_issue: {tuple(row)}")

        canonical = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='vocabulary_items'"
        ).fetchone()
        if canonical:
            print("canonical_manifest_counts:")
            for table in (
                "vocabulary_items",
                "book_entries",
                "item_examples",
                "item_marks",
                "item_source_notes",
            ):
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                print(f"  {table}: {count}")

            print("item_examples.kind counts:")
            for row in conn.execute(
                """
                SELECT kind, COUNT(*) AS count
                FROM item_examples
                GROUP BY kind
                ORDER BY kind
                """
            ):
                print(f"  {row['kind']}: {row['count']}")

            print("vocabulary_migration_reports:")
            for row in conn.execute(
                """
                SELECT kind, COUNT(*) AS groups, SUM(row_count) AS rows
                FROM vocabulary_migration_reports
                GROUP BY kind
                ORDER BY kind
                """
            ):
                print(f"  {row['kind']}: groups={row['groups']} rows={row['rows']}")
        else:
            print("entry_examples.kind counts:")
            for row in conn.execute(
                """
                SELECT kind, COUNT(*) AS count
                FROM entry_examples
                GROUP BY kind
                ORDER BY kind
                """
            ):
                print(f"  {row['kind']}: {row['count']}")

        mismatch_sql = """
            SELECT e.book_code, COUNT(*) AS count
            FROM entries e
            JOIN entry_examples x
              ON x.entry_id = e.entry_id
             AND (x.kind = 'main_sentence' OR x.position = 0)
            WHERE COALESCE(TRIM(e.sentence), '') <> COALESCE(TRIM(x.text), '')
            GROUP BY e.book_code
            ORDER BY e.book_code
        """
        mismatches = conn.execute(mismatch_sql).fetchall()
        print("main_sentence_compat_mismatches:")
        if mismatches:
            for row in mismatches:
                print(f"  {row['book_code']}: {row['count']}")
        else:
            print("  none")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
