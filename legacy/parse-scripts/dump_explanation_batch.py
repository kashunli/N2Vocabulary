#!/usr/bin/env python3
"""Step 2a: Print a batch of vocabulary entries for Claude Code to explain.

Usage:
    python parse/scripts/dump_explanation_batch.py [--batch 30] [--offset 0] [--skip-done]

Output is a formatted prompt block that can be fed back to Claude Code.
Each entry is printed with its index, headword, and sentence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="output/vocabulary_db.json")
    ap.add_argument("--batch", type=int, default=30)
    ap.add_argument("--offset", type=int, default=0,
                    help="Skip this many eligible entries before starting")
    ap.add_argument("--skip-done", action="store_true",
                    help="Skip entries that already have an explanation")
    args = ap.parse_args()

    db_path = ROOT / args.src
    db = json.loads(db_path.read_text(encoding="utf-8"))

    eligible = [e for e in db if not args.skip_done or e.get("explanation") is None]
    done_count = len(db) - len(eligible)
    batch = eligible[args.offset : args.offset + args.batch]

    if not batch:
        print(f"No entries to process (total={len(db)}, done={done_count}, offset={args.offset}).")
        return

    print(f"# Explanation batch  offset={args.offset}  count={len(batch)}  (done={done_count}/{len(db)})")
    print()
    print("Generate a JSON array with one object per entry below.")
    print('Format: [{"index": N, "explanation": "line1\\nline2\\n..."}, ...]')
    print()
    print("Rules per explanation:")
    print("- Go phrase by phrase in sentence order")
    print("- Format: phrase = \"translation\" — key terms glossed, grammar explained inline")
    print("- Note grammar patterns (e.g. たら-form, より, が-contrast) on their own line if noteworthy")
    print("- End with one 👉 Nuance: line")
    print("- Plain text only, max 12 lines, use \\n between lines")
    print()
    print("─" * 60)
    print()

    for e in batch:
        sentence = e["sentence"] or "(no sentence)"
        print(f'[{e["index"]}] {sentence}')
        print()

    print("─" * 60)
    print(f"# Output the JSON array for indexes {batch[0]['index']}–{batch[-1]['index']}")


if __name__ == "__main__":
    main()
