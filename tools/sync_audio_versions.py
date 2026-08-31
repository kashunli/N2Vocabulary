"""Persist SHA-256 identities for the audio clips referenced by the runtime DB.

Run this after an importer or audio repair has copied/replaced MP3 files. The
size and nanosecond mtime columns make repeated runs cheap: unchanged files are
not read or hashed again. The Rust service only reads ``audio_versions`` at
runtime and never calculates an audio digest.
"""

from __future__ import annotations

import argparse
import hashlib
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def sync(db_path: Path, clips_root: Path) -> tuple[int, int, int]:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audio_versions (
              clip_path TEXT PRIMARY KEY,
              sha256 TEXT NOT NULL,
              file_size INTEGER NOT NULL,
              modified_ns INTEGER NOT NULL,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cached = {
            row[0]: (row[1], row[2], row[3])
            for row in conn.execute(
                "SELECT clip_path, sha256, file_size, modified_ns FROM audio_versions"
            )
        }
        checked = changed = missing = 0
        for clip_path in sorted(collect_clip_paths(conn)):
            checked += 1
            path = clips_root.parent / clip_path
            try:
                stat = path.stat()
            except FileNotFoundError:
                conn.execute("DELETE FROM audio_versions WHERE clip_path = ?", (clip_path,))
                missing += 1
                continue
            if not path.is_file():
                conn.execute("DELETE FROM audio_versions WHERE clip_path = ?", (clip_path,))
                missing += 1
                continue
            cached_row = cached.get(clip_path)
            if cached_row and cached_row[1:] == (stat.st_size, stat.st_mtime_ns):
                continue
            digest = sha256_file(path)
            conn.execute(
                """
                INSERT INTO audio_versions(clip_path, sha256, file_size, modified_ns)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(clip_path) DO UPDATE SET
                  sha256 = excluded.sha256,
                  file_size = excluded.file_size,
                  modified_ns = excluded.modified_ns,
                  updated_at = CURRENT_TIMESTAMP
                """,
                (clip_path, digest, stat.st_size, stat.st_mtime_ns),
            )
            changed += 1
        conn.commit()
        return checked, changed, missing
    finally:
        conn.close()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=root / "wordService" / "data" / "n2vocab.sqlite")
    parser.add_argument("--clips-root", type=Path, default=root / "clips")
    args = parser.parse_args()
    checked, changed, missing = sync(args.db, args.clips_root)
    print(f"checked={checked} changed={changed} missing={missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
