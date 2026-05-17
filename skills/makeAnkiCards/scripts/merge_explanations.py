#!/usr/bin/env python3
"""Merge a batch of explanations (JSON array) into vocabulary.json.

Usage:
    python skills/makeAnkiCards/scripts/merge_explanations.py <explanations.json>

The input JSON should be an array of {"index": N, "explanation": "..."} objects.
Entries whose index is not found in the DB are reported as warnings.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="JSON file with [{index, explanation}, ...] array")
    ap.add_argument("--db", default="vocabulary.json")
    args = ap.parse_args()

    db_path = ROOT / args.db
    db = json.loads(db_path.read_text(encoding="utf-8"))
    idx_map = {e["index"]: i for i, e in enumerate(db)}

    batch = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(batch, list):
        print("Error: input must be a JSON array", file=sys.stderr)
        sys.exit(1)

    updated = 0
    for item in batch:
        idx = item.get("index")
        exp = item.get("explanation")
        if idx is None or exp is None:
            print(f"  Warning: skipping malformed item {item!r}")
            continue
        if idx not in idx_map:
            print(f"  Warning: index {idx} not found in DB")
            continue
        db[idx_map[idx]]["explanation"] = exp
        updated += 1

    db_path.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")

    total   = len(db)
    done    = sum(1 for e in db if e.get("explanation") is not None)
    print(f"Updated {updated} entries.  Progress: {done}/{total} explained ({done*100//total}%)")


if __name__ == "__main__":
    main()
