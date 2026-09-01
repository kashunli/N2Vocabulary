"""Persist unique database IDs for audio clips referenced by the runtime DB.

Run this after an importer or audio repair has copied/replaced MP3 files. The
size and nanosecond mtime columns make repeated runs cheap: unchanged files
keep their existing ``audio_id`` and are not read at all. A new or changed
file receives a new SQLite AUTOINCREMENT ID, which invalidates the browser's
decoded-audio cache without hashing the MP3 at runtime or during sync.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def normalize_clip_path(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.replace("\\", "/").lstrip("/")
    if normalized.startswith("output/clips/"):
        normalized = "clips/" + normalized[len("output/clips/") :]
    if not normalized.startswith("clips/"):
        return None
    parts = normalized.split("/")
    if any(not part or part in {".", ".."} or ":" in part for part in parts):
        return None
    return normalized


def collect_clip_paths(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        """
        SELECT word_clip AS clip_path FROM vocabulary_items
        UNION SELECT word_clip FROM book_entries
        UNION SELECT sentence_clip FROM book_entries
        UNION SELECT audio_clip FROM item_examples
        """
    )
    return {
        normalized
        for row in rows
        if (normalized := normalize_clip_path(row[0])) is not None
    }


def ensure_audio_assets_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audio_assets (
          audio_id INTEGER PRIMARY KEY AUTOINCREMENT,
          clip_path TEXT NOT NULL UNIQUE,
          file_size INTEGER NOT NULL,
          modified_ns INTEGER NOT NULL,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # Keep this script usable when run directly against a database that has
    # only migration 011 applied. The migration itself performs the same
    # metadata-only conversion; this fallback never opens an audio file.
    has_legacy_table = conn.execute(
        "SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type='table' AND name='audio_versions')"
    ).fetchone()[0]
    if has_legacy_table:
        conn.execute(
            """
            INSERT OR IGNORE INTO audio_assets(clip_path, file_size, modified_ns, updated_at)
            SELECT clip_path, file_size, modified_ns, updated_at
            FROM audio_versions
            """
        )
        conn.execute("DROP TABLE audio_versions")


def sync(db_path: Path, clips_root: Path) -> tuple[int, int, int]:
    conn = sqlite3.connect(db_path)
    try:
        ensure_audio_assets_table(conn)
        cached = {
            row[0]: (row[1], row[2], row[3])
            for row in conn.execute(
                "SELECT clip_path, audio_id, file_size, modified_ns FROM audio_assets"
            )
        }
        checked = changed = missing = 0
        for clip_path in sorted(collect_clip_paths(conn)):
            checked += 1
            path = clips_root.parent / clip_path
            try:
                stat = path.stat()
            except FileNotFoundError:
                conn.execute("DELETE FROM audio_assets WHERE clip_path = ?", (clip_path,))
                missing += 1
                continue
            if not path.is_file():
                conn.execute("DELETE FROM audio_assets WHERE clip_path = ?", (clip_path,))
                missing += 1
                continue
            cached_row = cached.get(clip_path)
            if cached_row and cached_row[1:] == (stat.st_size, stat.st_mtime_ns):
                continue

            # Replacing the row, rather than updating it in place, is
            # intentional: AUTOINCREMENT guarantees a changed clip gets a new
            # cache key even when its size and mtime happen to be unchanged.
            conn.execute("DELETE FROM audio_assets WHERE clip_path = ?", (clip_path,))
            conn.execute(
                """
                INSERT INTO audio_assets(clip_path, file_size, modified_ns)
                VALUES (?, ?, ?)
                """,
                (clip_path, stat.st_size, stat.st_mtime_ns),
            )
            changed += 1
        conn.commit()
        return checked, changed, missing
    finally:
        conn.close()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", type=Path, default=root / "wordService" / "data" / "n2vocab.sqlite"
    )
    parser.add_argument("--clips-root", type=Path, default=root / "clips")
    args = parser.parse_args()
    checked, changed, missing = sync(args.db, args.clips_root)
    print(f"checked={checked} changed={changed} missing={missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
