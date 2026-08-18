#!/usr/bin/env python3
"""Relocate GWB_N2 word clips out of the TTS folder into clips/gwb_n2/words/.

GWB_N2's word clips are human-read audio that was stored under
clips/generated_sentences/edge_tts/ (e.g. word2030.mp3). This script:

  1. enumerates the exact GWB_N2 word_clip paths from the DB,
  2. backs up the DB (SQLite online backup API, safe while the service runs),
  3. moves each file into clips/gwb_n2/words/,
  4. updates book_entries.word_clip for GWB_N2 rows,
  5. verifies no missing files and no leftover old-path references.

Run with --dry-run first to preview. Other books / example TTS are untouched.
"""

import argparse
import datetime
import os
import sqlite3
import sys
from collections import Counter

SRC_PREFIX = "clips/generated_sentences/edge_tts/"
DST_DIR = "clips/gwb_n2/words"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="repo root (default: cwd)")
    parser.add_argument("--db", default="wordService/data/n2vocab.sqlite")
    parser.add_argument("--dry-run", action="store_true", help="preview without changing anything")
    args = parser.parse_args()

    root = os.path.abspath(args.repo_root)
    db_path = os.path.join(root, args.db)
    if not os.path.exists(db_path):
        print(f"FATAL: DB not found: {db_path}")
        return 1

    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=10000")

    rows = conn.execute(
        "SELECT entry_id, word_clip FROM book_entries "
        "WHERE book_code='GWB_N2' AND word_clip IS NOT NULL"
    ).fetchall()

    moves: list[tuple[int, str, str]] = []
    for row in rows:
        wc = row["word_clip"]
        if not wc.startswith(SRC_PREFIX):
            print(f"SKIP unexpected non-edge_tts word_clip: {wc} (entry {row['entry_id']})")
            continue
        # DB paths use forward slashes; os.path.join would inject a backslash on Windows.
        dst = f"{DST_DIR}/{os.path.basename(wc)}"
        moves.append((row["entry_id"], wc, dst))

    if not moves:
        print("Nothing to move.")
        return 0

    # Pre-flight validation.
    missing_src = [m for m in moves if not os.path.exists(os.path.join(root, m[1]))]
    if missing_src:
        print(f"FATAL: {len(missing_src)} source files missing on disk; aborting")
        for _, src, _ in missing_src[:10]:
            print("  ", src)
        return 1

    existing_targets = [m for m in moves if os.path.exists(os.path.join(root, m[2]))]
    if existing_targets:
        print(f"FATAL: {len(existing_targets)} target files already exist; aborting")
        for _, _, dst in existing_targets[:10]:
            print("  ", dst)
        return 1

    dupes = [dst for dst, count in Counter(m[2] for m in moves).items() if count > 1]
    if dupes:
        print(f"FATAL: duplicate target paths: {dupes[:5]}")
        return 1

    print(f"Plan: move {len(moves)} files from {SRC_PREFIX}* -> {DST_DIR}/, then update the DB.")
    if args.dry_run:
        print("Dry run — no changes made.")
        return 0

    # Backup the DB via SQLite's online backup API (consistent while the service runs).
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"{db_path}.backup_before_gwb_word_audio_move_{ts}"
    backup_conn = sqlite3.connect(backup)
    conn.backup(backup_conn)
    backup_conn.close()
    print(f"Backed up DB -> {os.path.relpath(backup, root)}")

    os.makedirs(os.path.join(root, DST_DIR), exist_ok=True)

    # Move files; roll everything back if any single move fails.
    moved: list[tuple[int, str, str]] = []
    failures: list[tuple[str, str]] = []
    for entry_id, src, dst in moves:
        try:
            os.rename(os.path.join(root, src), os.path.join(root, dst))
            moved.append((entry_id, src, dst))
        except OSError as exc:
            failures.append((src, str(exc)))

    if failures:
        for entry_id, src, dst in reversed(moved):
            try:
                os.rename(os.path.join(root, dst), os.path.join(root, src))
            except OSError:
                pass
        print(f"FATAL: {len(failures)} files failed to move; rolled back {len(moved)}. Examples:")
        for src, err in failures[:5]:
            print("  ", src, "->", err)
        return 1

    print(f"Moved {len(moved)} files.")

    # Update DB paths in one transaction.
    conn.execute("BEGIN")
    for entry_id, src, dst in moved:
        conn.execute(
            "UPDATE book_entries SET word_clip=? WHERE entry_id=? AND book_code='GWB_N2' AND word_clip=?",
            (dst, entry_id, src),
        )
    conn.commit()
    print(f"Updated {len(moved)} DB rows.")

    # Verify.
    leftover = conn.execute(
        "SELECT count(*) FROM book_entries WHERE book_code='GWB_N2' AND word_clip LIKE ?",
        (SRC_PREFIX + "%",),
    ).fetchone()[0]
    new_rows = conn.execute(
        "SELECT count(*) FROM book_entries WHERE book_code='GWB_N2' AND word_clip LIKE ?",
        (DST_DIR + "/%",),
    ).fetchone()[0]
    missing_after = [m for m in moves if not os.path.exists(os.path.join(root, m[2]))]

    print(
        f"Verify: leftover old-path rows={leftover}, new-path rows={new_rows}, "
        f"missing files after move={len(missing_after)}"
    )
    conn.close()

    if leftover or new_rows != len(moved) or missing_after:
        print("WARNING: verification failed — inspect the state above.")
        return 2

    print("Done. GWB_N2 word clips now live under clips/gwb_n2/words/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
