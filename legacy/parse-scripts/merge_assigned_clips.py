#!/usr/bin/env python3
"""merge_assigned_clips.py — Merge assign_track_clips.py output into vocabulary_db.json.

Usage:
    python parse/scripts/merge_assigned_clips.py output/review_assigned.json

For each entry in the review JSON that has valid word_clip and sentence_clip paths,
this script updates the corresponding entry in vocabulary_db.json.

Entries with match_method="none" (no audio found) are left unchanged — they keep
their existing clip paths or null if they had none.
"""
import json, sys, shutil
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "output" / "vocabulary_db.json"


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Usage: python merge_assigned_clips.py <review_assigned.json>")

    review_path = Path(sys.argv[1])
    review = json.loads(review_path.read_text(encoding="utf-8"))

    db = json.loads(DB_PATH.read_text(encoding="utf-8"))
    by_index = {e["index"]: e for e in db}

    updated  = 0
    skipped  = 0
    no_match = 0

    for r in review:
        idx = r["index"]
        entry = by_index.get(idx)
        if entry is None:
            continue

        method = r.get("match_method", "none")
        wclip  = r.get("word_clip")
        sclip  = r.get("sentence_clip")

        if method == "none" or not wclip or not sclip:
            no_match += 1
            continue

        # Validate the clip files actually exist.
        wp = ROOT / wclip
        sp = ROOT / sclip
        if not wp.exists() or not sp.exists():
            print(f"[WARN] [{idx}] clip files missing, skipping", flush=True)
            skipped += 1
            continue

        entry["word_clip"]     = wclip
        entry["sentence_clip"] = sclip
        updated += 1

    # Back up then write.
    shutil.copy(DB_PATH, str(DB_PATH) + ".bak")
    DB_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")

    total = len(review)
    print(f"vocabulary_db.json updated:")
    print(f"  Updated clip paths : {updated}/{total}")
    print(f"  No match (skipped) : {no_match}")
    print(f"  Missing files      : {skipped}")
    print(f"  Backup             : {DB_PATH}.bak")


if __name__ == "__main__":
    main()
