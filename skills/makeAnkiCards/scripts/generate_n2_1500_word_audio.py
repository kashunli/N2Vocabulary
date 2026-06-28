#!/usr/bin/env python3
"""Generate dedicated N2_1500 word audio from kana readings.

This is intentionally scoped to the N2_1500 Anki-export repair. The original
book does not have trustworthy source word clips, and generating from kanji can
make TTS choose the wrong reading. We synthesize from the SQLite `reading`
field instead, then write explicit `entries.word_clip` paths so the deck
builder never has to fall back to same-number clips from another book.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TTS_SCRIPT_ROOT = PROJECT_ROOT / "skills" / "microsoft-edge-japanese-tts" / "scripts"
if str(TTS_SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(TTS_SCRIPT_ROOT))

from generate_edge_tts import DEFAULT_RATE, DEFAULT_VOICE, import_edge_tts, synthesize_one

BOOK_CODE = "N2_1500"
DEFAULT_DB = PROJECT_ROOT / "wordService" / "data" / "n2vocab.sqlite"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "clips" / "n2_1500" / "words"
RELATIVE_CLIP_PREFIX = "clips/n2_1500/words"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate N2_1500 word audio from kana readings.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--voice", default=DEFAULT_VOICE)
    parser.add_argument("--rate", default=DEFAULT_RATE)
    parser.add_argument("--pitch", default="+0Hz")
    parser.add_argument("--limit", type=int, help="Generate only the first N matching rows.")
    parser.add_argument("--source-indexes", help="Generate only source indexes like 333,788,1409-1423.")
    parser.add_argument("--force", action="store_true", help="Regenerate existing MP3 files.")
    parser.add_argument("--dry-run", action="store_true", help="Write the plan but do not synthesize or update SQLite.")
    parser.add_argument("--manifest", type=Path, help="Manifest path. Defaults inside the output directory.")
    return parser.parse_args()


def parse_source_indexes(value: str | None) -> set[int]:
    if not value:
        return set()
    indexes: set[int] = set()
    for part in value.split(","):
        item = part.strip()
        if not item:
            continue
        if "-" in item:
            start_text, end_text = item.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            indexes.update(range(start, end + 1))
        else:
            indexes.add(int(item))
    return indexes


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def load_entries(db_path: Path, limit: int | None, source_indexes: set[int]) -> list[sqlite3.Row]:
    conn = connect(db_path)
    try:
        sql = """
            SELECT entry_id, source_index, kanji, reading, word_clip
              FROM entries
             WHERE book_code = ?
               AND trim(coalesce(reading, '')) <> ''
             ORDER BY unit_number, position, source_index
        """
        rows = conn.execute(sql, (BOOK_CODE,)).fetchall()
    finally:
        conn.close()
    if source_indexes:
        rows = [row for row in rows if int(row["source_index"]) in source_indexes]
    return rows[:limit] if limit is not None else rows


def output_path_for(row: sqlite3.Row, output_dir: Path) -> Path:
    return output_dir / f"n2_1500_word_{int(row['entry_id']):04d}.mp3"


def relative_clip_for(path: Path) -> str:
    return f"{RELATIVE_CLIP_PREFIX}/{path.name}"


def reading_for_tts(reading: str) -> str:
    """Remove notation markers that should be visible on cards but not spoken."""
    cleaned = str(reading or "")
    cleaned = re.sub(r"[（）()［］\[\]]", "", cleaned)
    cleaned = cleaned.replace("～", "").replace("~", "")
    cleaned = cleaned.replace("／", "").replace("/", "")
    cleaned = re.sub(r"\s+", "", cleaned)
    return cleaned.strip()


def update_db(db_path: Path, generated: list[dict[str, Any]]) -> int:
    rows = [
        (item["relative_clip"], int(item["entry_id"]))
        for item in generated
        if item.get("status") in {"generated", "skipped_existing"}
    ]
    conn = connect(db_path)
    try:
        conn.executemany("UPDATE entries SET word_clip = ? WHERE entry_id = ?", rows)
        conn.commit()
    finally:
        conn.close()
    return len(rows)


async def run(args: argparse.Namespace) -> int:
    rows = load_entries(args.db, args.limit, parse_source_indexes(args.source_indexes))
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.manifest or output_dir / "_n2_1500_word_tts_manifest.json"

    edge_tts = None if args.dry_run else import_edge_tts()
    manifest: list[dict[str, Any]] = []

    for index, row in enumerate(rows, start=1):
        output_path = output_path_for(row, output_dir)
        relative_clip = relative_clip_for(output_path)
        tts_text = reading_for_tts(str(row["reading"]))
        record = {
            "entry_id": int(row["entry_id"]),
            "source_index": int(row["source_index"]),
            "kanji": row["kanji"],
            "reading": row["reading"],
            "text_used_for_tts": tts_text,
            "file": str(output_path),
            "relative_clip": relative_clip,
            "voice": args.voice,
            "rate": args.rate,
            "pitch": args.pitch,
        }

        print(f"[{index}/{len(rows)}] {row['source_index']} {row['kanji']} -> {tts_text}")
        if args.dry_run:
            record["status"] = "dry_run"
        elif output_path.exists() and not args.force:
            record["status"] = "skipped_existing"
        else:
            try:
                await synthesize_one(edge_tts, tts_text, output_path, args)
                record["status"] = "generated"
            except Exception as exc:  # pragma: no cover - service/network dependent
                record["status"] = "error"
                record["error"] = str(exc)
        manifest.append(record)

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.dry_run:
        print(f"dry-run manifest -> {manifest_path}")
        return 0

    errors = [item for item in manifest if item.get("status") == "error"]
    if errors:
        print(f"ERROR: {len(errors)} synthesis failures; manifest -> {manifest_path}", file=sys.stderr)
        return 1

    updated = update_db(args.db, manifest)
    print(f"manifest -> {manifest_path}")
    print(f"updated word_clip rows: {updated}")
    return 0


def main() -> int:
    return asyncio.run(run(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
