#!/usr/bin/env python3
"""Generate dedicated N2_1500 related-form/example audio.

N2_1500 related forms live in `entry_examples` as structured study examples.
Some rows have a reading annotation for only the added part of a compound, so
this script chooses the spoken TTS text carefully instead of blindly speaking
either kanji or the raw reading field.
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

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from generate_edge_tts import DEFAULT_RATE, DEFAULT_VOICE, import_edge_tts, synthesize_one
from generate_n2_1500_word_audio import parse_source_indexes, reading_for_tts

BOOK_CODE = "N2_1500"
DEFAULT_DB = PROJECT_ROOT / "wordService" / "data" / "n2vocab.sqlite"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "clips" / "n2_1500" / "examples"
RELATIVE_CLIP_PREFIX = "clips/n2_1500/examples"
FORM_SPLIT_RE = re.compile(r"[・／/]")
KANA_SUFFIX_RE = re.compile(r"([ぁ-んァ-ンー]+)$")
KANA_RE = re.compile(r"[ぁ-んァ-ンー]")
INLINE_READING_RE = re.compile(r"[［\[]([^］\]]+)[］\]]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate N2_1500 example/term audio.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--voice", default=DEFAULT_VOICE)
    parser.add_argument("--rate", default=DEFAULT_RATE)
    parser.add_argument("--pitch", default="+0Hz")
    parser.add_argument("--limit", type=int, help="Generate only the first N matching rows.")
    parser.add_argument("--source-indexes", help="Generate only source indexes like 1-10,62,333.")
    parser.add_argument("--force", action="store_true", help="Regenerate existing MP3 files.")
    parser.add_argument("--dry-run", action="store_true", help="Write the plan but do not synthesize or update SQLite.")
    parser.add_argument("--manifest", type=Path, help="Manifest path. Defaults inside the output directory.")
    return parser.parse_args()


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def load_examples(db_path: Path, limit: int | None, source_indexes: set[int]) -> list[sqlite3.Row]:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT
              e.entry_id,
              e.source_index,
              e.kanji,
              e.reading AS entry_reading,
              x.position,
              x.category,
              x.text,
              x.reading AS example_reading,
              x.translation_zh,
              x.audio_clip
            FROM entry_examples x
            JOIN entries e ON e.entry_id = x.entry_id
            WHERE e.book_code = ?
              AND trim(coalesce(x.text, '')) <> ''
            ORDER BY e.unit_number, e.position, e.source_index, x.position
            """,
            (BOOK_CODE,),
        ).fetchall()
    finally:
        conn.close()
    if source_indexes:
        rows = [row for row in rows if int(row["source_index"]) in source_indexes]
    return rows[:limit] if limit is not None else rows


def output_path_for(row: sqlite3.Row, output_dir: Path) -> Path:
    return output_dir / f"n2_1500_ex_{int(row['entry_id']):04d}_{int(row['position']):02d}.mp3"


def relative_clip_for(path: Path) -> str:
    return f"{RELATIVE_CLIP_PREFIX}/{path.name}"


def display_forms(value: str) -> list[str]:
    """Return searchable display variants from a headword like `捉える／捕らえる`."""
    cleaned = re.sub(r"[（(].*?[）)]", "", str(value or ""))
    return [part for part in FORM_SPLIT_RE.split(cleaned) if part]


def complete_reading_with_visible_kana(text: str, reading: str) -> str:
    """Append visible kana okurigana when a source reading annotates only kanji.

    Source lines can contain shapes like `間違[まちが]い`: after removing the
    bracket annotation the text is `間違い`, while the stored reading is only
    `まちが`. The final `い` is already visible, so we add it for TTS.
    """
    m = KANA_SUFFIX_RE.search(str(text or ""))
    if not m:
        return reading
    suffix = m.group(1)
    return reading if reading.endswith(suffix) else reading + suffix


def append_tail_okurigana(tail: str, reading: str) -> str:
    """Append kana at the end of a compound tail such as `入り` -> `いり`."""
    m = KANA_SUFFIX_RE.search(str(tail or ""))
    if not m:
        return reading
    suffix = m.group(1)
    return reading if reading.endswith(suffix) else reading + suffix


def base_reading_for_compound(row: sqlite3.Row, form: str) -> str:
    """Return the entry reading to use when the entry is part of a compound."""
    reading = reading_for_tts(str(row["entry_reading"] or ""))
    # Headwords like 訪問（する） store readings like ほうもん（する）. In compounds
    # such as 訪問客, the noun stem is used, not the suru-verb form.
    if "する" not in form and reading.endswith("する"):
        reading = reading[:-2]
    return reading


def inline_reading_for_tts(text: str) -> str:
    """Use full-width/square bracket readings embedded in source text."""
    readings = [reading_for_tts(match.group(1)) for match in INLINE_READING_RE.finditer(str(text or ""))]
    return "".join(item for item in readings if item)


def choose_tts_text(row: sqlite3.Row) -> str:
    """Choose spoken text for a related-form row.

    Reading annotations may be full readings (`足跡 [あしあと]`) or just the
    added compound piece (`一致点 [てん]`). When the example visibly starts or
    ends with the entry word, combine the entry reading with that piece.
    """
    text = str(row["text"] or "").strip()
    inline_reading = inline_reading_for_tts(text)
    if inline_reading:
        return inline_reading

    if row["category"] in {"連", "慣"}:
        return text

    raw_source_reading = str(row["example_reading"] or "")
    if "/" in raw_source_reading and KANA_RE.search(text):
        return text

    raw_reading = reading_for_tts(raw_source_reading)
    if not raw_reading:
        return text

    for form in display_forms(str(row["kanji"] or "")):
        if not form or form not in text:
            continue
        entry_reading = base_reading_for_compound(row, form)
        if text == form:
            return entry_reading or complete_reading_with_visible_kana(text, raw_reading)
        if text.startswith(form) and entry_reading and not raw_reading.startswith(entry_reading):
            return entry_reading + append_tail_okurigana(text[len(form):], raw_reading)
        if text.endswith(form) and entry_reading and not raw_reading.endswith(entry_reading):
            return raw_reading + entry_reading
    return complete_reading_with_visible_kana(text, raw_reading)


def update_db(db_path: Path, generated: list[dict[str, Any]]) -> int:
    rows = [
        (item["relative_clip"], int(item["entry_id"]), int(item["position"]))
        for item in generated
        if item.get("status") in {"generated", "skipped_existing"}
    ]
    conn = connect(db_path)
    try:
        conn.executemany(
            "UPDATE entry_examples SET audio_clip = ? WHERE entry_id = ? AND position = ?",
            rows,
        )
        conn.commit()
    finally:
        conn.close()
    return len(rows)


async def run(args: argparse.Namespace) -> int:
    rows = load_examples(args.db, args.limit, parse_source_indexes(args.source_indexes))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.manifest or args.output_dir / "_n2_1500_example_tts_manifest.json"
    edge_tts = None if args.dry_run else import_edge_tts()
    manifest: list[dict[str, Any]] = []

    for index, row in enumerate(rows, start=1):
        output_path = output_path_for(row, args.output_dir)
        relative_clip = relative_clip_for(output_path)
        tts_text = choose_tts_text(row)
        record = {
            "entry_id": int(row["entry_id"]),
            "source_index": int(row["source_index"]),
            "position": int(row["position"]),
            "category": row["category"],
            "headword": row["kanji"],
            "text": row["text"],
            "example_reading": row["example_reading"],
            "text_used_for_tts": tts_text,
            "file": str(output_path),
            "relative_clip": relative_clip,
            "voice": args.voice,
            "rate": args.rate,
            "pitch": args.pitch,
        }
        print(
            f"[{index}/{len(rows)}] #{row['source_index']} pos {row['position']} "
            f"{row['text']} -> {tts_text}"
        )

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
    print(f"updated entry_examples audio rows: {updated}")
    return 0


def main() -> int:
    return asyncio.run(run(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
