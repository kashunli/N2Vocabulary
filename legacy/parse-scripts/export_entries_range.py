#!/usr/bin/env python3
"""Export a normalized entry range for alignment and prompt generation.

This helper slices `output/vocabulary_combined.json` into the compact shape
expected by `align_track_by_llm.py`:

    - index
    - unit_number
    - headword
    - reading
    - sentence

It is especially useful for the unit-bounded sequential workflow, where one
candidate file can cover an entire unit and then be reused track by track.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Export a normalized inclusive entry range from vocabulary_combined.json.",
    )
    ap.add_argument(
        "--start",
        type=int,
        required=True,
        help="First inclusive entry index to export.",
    )
    ap.add_argument(
        "--end",
        type=int,
        required=True,
        help="Last inclusive entry index to export.",
    )
    ap.add_argument(
        "--output",
        type=str,
        required=True,
        help="Destination JSON path, relative to repo root unless absolute.",
    )
    ap.add_argument(
        "--input-json",
        type=str,
        default="output/vocabulary_combined.json",
        help="Source JSON path. Defaults to output/vocabulary_combined.json.",
    )
    return ap


def _resolve_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def _normalize_row(row: dict) -> dict:
    unit_number = row.get("unit_number")
    if unit_number is None:
        unit_number = row.get("unit", {}).get("number")
    headword = row.get("headword")
    if headword is None:
        headword = row.get("headword_text")
    sentence = row.get("sentence")
    if sentence is None:
        sentence = row.get("sentence_text")
    return {
        "index": row["index"],
        "unit_number": unit_number,
        "headword": headword or "",
        "reading": row.get("reading", "") or "",
        "sentence": sentence or "",
    }


def main() -> None:
    args = _build_parser().parse_args()
    if args.start > args.end:
        raise SystemExit("--start must be <= --end")

    input_path = _resolve_path(args.input_json)
    output_path = _resolve_path(args.output)
    rows = json.loads(input_path.read_text(encoding="utf-8"))

    selected = [
        _normalize_row(row)
        for row in rows
        if args.start <= int(row["index"]) <= args.end
    ]
    selected.sort(key=lambda item: item["index"])

    expected_count = args.end - args.start + 1
    if len(selected) != expected_count:
        found = {item["index"] for item in selected}
        missing = [idx for idx in range(args.start, args.end + 1) if idx not in found]
        raise SystemExit(
            f"Expected {expected_count} entries for {args.start}-{args.end}, "
            f"but found {len(selected)}. Missing indices: {missing[:10]}"
            + (" ..." if len(missing) > 10 else "")
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(selected, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {len(selected)} entries to {output_path} "
        f"(indices {selected[0]['index']}-{selected[-1]['index']})"
    )


if __name__ == "__main__":
    main()
