#!/usr/bin/env python3
"""Generate Japanese MP3 files with Microsoft Edge TTS.

This script is intentionally small and dependency-light so future agents can
reuse it for new example-sentence batches without re-writing Edge TTS glue.

Input modes:
  - --text "..." for one sentence
  - --input sentences.txt, one sentence per line
  - --input sentences.json or sentences.jsonl, strings or objects

For text files, an optional leading ID can be supplied as:
  id<TAB>sentence text
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_VOICE = "ja-JP-NanamiNeural"
DEFAULT_RATE = "-10%"
DEFAULT_TEXT_FIELDS = ("sentence", "text", "ja", "japanese")
DEFAULT_ID_FIELDS = ("id", "entry_id", "index", "source_index")
RATE_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?%$")
PITCH_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?Hz$")


def import_edge_tts():
    """Import lazily so --help works even before edge-tts is installed."""
    try:
        import edge_tts  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: edge-tts. Install it with:\n"
            "  python -m pip install edge-tts"
        ) from exc
    return edge_tts


def normalize_dash_value_args(argv: list[str]) -> list[str]:
    """Allow PowerShell-friendly forms like `--rate -10%`.

    argparse can interpret a value beginning with `-` as another option. Turning
    it into `--rate=-10%` keeps both human-friendly and parser-friendly forms.
    """
    normalized: list[str] = []
    i = 0
    while i < len(argv):
        current = argv[i]
        if current == "--rate" and i + 1 < len(argv) and RATE_RE.match(argv[i + 1]):
            normalized.append(f"--rate={argv[i + 1]}")
            i += 2
            continue
        if current == "--pitch" and i + 1 < len(argv) and PITCH_RE.match(argv[i + 1]):
            normalized.append(f"--pitch={argv[i + 1]}")
            i += 2
            continue
        normalized.append(current)
        i += 1
    return normalized


def sanitize_filename(value: str) -> str:
    """Keep filenames Windows-safe while preserving readable IDs."""
    cleaned = re.sub(r'[<>:"/\\\\|?*\\x00-\\x1f]+', "_", value.strip())
    cleaned = re.sub(r"\\s+", "_", cleaned).strip("._ ")
    return cleaned[:120] or "sentence"


def first_present(row: dict[str, Any], fields: tuple[str, ...]) -> Any:
    for field in fields:
        value = row.get(field)
        if value is not None and str(value).strip():
            return value
    return None


def item_from_value(value: Any, position: int, text_fields: tuple[str, ...]) -> dict[str, str]:
    """Normalize string/dict JSON rows into the script's tiny item contract."""
    if isinstance(value, str):
        return {"id": f"{position:04d}", "text": value.strip()}

    if not isinstance(value, dict):
        raise ValueError(f"Item {position} is not a string or object: {value!r}")

    text = first_present(value, text_fields)
    if text is None:
        raise ValueError(f"Item {position} has no text field in {text_fields}: {value!r}")

    item_id = first_present(value, DEFAULT_ID_FIELDS)
    if item_id is None:
        item_id = f"{position:04d}"

    return {"id": str(item_id), "text": str(text).strip()}


def load_text_file(path: Path) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # A tab-separated leading ID gives stable filenames without needing JSON.
        if "\t" in line:
            item_id, text = line.split("\t", 1)
            item_id = item_id.strip() or f"{line_number:04d}"
            text = text.strip()
        else:
            item_id = f"{line_number:04d}"
            text = line

        if text:
            items.append({"id": item_id, "text": text})
    return items


def load_json_file(path: Path, text_fields: tuple[str, ...]) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict):
        # Common manifest shapes put the real rows under one of these keys.
        for key in ("items", "sentences", "entries", "data"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
        else:
            payload = [payload]

    if not isinstance(payload, list):
        raise ValueError("JSON input must be a list, object, or object containing an items/sentences/entries/data list")

    return [item_from_value(value, index, text_fields) for index, value in enumerate(payload, start=1)]


def load_jsonl_file(path: Path, text_fields: tuple[str, ...]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        items.append(item_from_value(json.loads(line), line_number, text_fields))
    return items


def load_items(args: argparse.Namespace) -> list[dict[str, str]]:
    text_fields = tuple(field.strip() for field in args.text_field.split(",") if field.strip())

    if args.text:
        return [{"id": args.id or "0001", "text": args.text.strip()}]

    input_path = Path(args.input).expanduser()
    suffix = input_path.suffix.lower()
    if suffix == ".json":
        return load_json_file(input_path, text_fields)
    if suffix == ".jsonl":
        return load_jsonl_file(input_path, text_fields)
    return load_text_file(input_path)


def output_path_for(item: dict[str, str], args: argparse.Namespace, position: int) -> Path:
    if args.out:
        if position != 1:
            raise ValueError("--out can only be used with one input sentence")
        return Path(args.out).expanduser()

    output_dir = Path(args.output_dir).expanduser()
    filename = f"{args.prefix}{sanitize_filename(item['id'])}.mp3"
    return output_dir / filename


async def synthesize_one(edge_tts: Any, text: str, output_path: Path, args: argparse.Namespace) -> None:
    """Generate one MP3 atomically so interrupted runs do not leave partial files."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_name(f"{output_path.stem}.tmp{output_path.suffix}")
    if tmp_path.exists():
        tmp_path.unlink()

    communicate = edge_tts.Communicate(
        text=text,
        voice=args.voice,
        rate=args.rate,
        pitch=args.pitch,
    )
    await communicate.save(str(tmp_path))

    if output_path.exists():
        output_path.unlink()
    tmp_path.replace(output_path)


async def run(args: argparse.Namespace) -> int:
    items = [item for item in load_items(args) if item["text"]]
    if not items:
        print("No non-empty sentences found.", file=sys.stderr)
        return 1

    if args.out and len(items) != 1:
        print("--out can only be used with exactly one sentence.", file=sys.stderr)
        return 1

    edge_tts = None if args.dry_run else import_edge_tts()
    manifest: list[dict[str, Any]] = []

    for position, item in enumerate(items, start=1):
        output_path = output_path_for(item, args, position)
        record = {
            "id": item["id"],
            "text": item["text"],
            "voice": args.voice,
            "rate": args.rate,
            "pitch": args.pitch,
            "file": str(output_path),
        }

        if output_path.exists() and not args.force:
            record["status"] = "skipped_existing"
            print(f"[skip] {item['id']} -> {output_path}")
            manifest.append(record)
            continue

        if args.dry_run:
            record["status"] = "dry_run"
            print(f"[dry-run] {item['id']} -> {output_path}")
            manifest.append(record)
            continue

        try:
            await synthesize_one(edge_tts, item["text"], output_path, args)
            record["status"] = "generated"
            print(f"[ok] {item['id']} -> {output_path}")
        except Exception as exc:  # pragma: no cover - network/service failures vary
            record["status"] = "error"
            record["error"] = str(exc)
            manifest.append(record)
            if not args.keep_going:
                raise
            print(f"[error] {item['id']}: {exc}", file=sys.stderr)
            continue

        manifest.append(record)

    manifest_path = Path(args.manifest).expanduser() if args.manifest else Path(args.output_dir).expanduser() / "_edge_tts_manifest.json"
    if args.out and not args.manifest:
        manifest_path = output_path_for(items[0], args, 1).with_suffix(".manifest.json")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"manifest -> {manifest_path}")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    argv = normalize_dash_value_args(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description="Generate Japanese MP3 audio with Microsoft Edge TTS.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="Single Japanese sentence to synthesize.")
    source.add_argument("--input", help="Input .txt, .json, or .jsonl file.")
    parser.add_argument("--id", help="Stable ID/filename stem for --text mode.")
    parser.add_argument("--out", help="Output MP3 path for --text mode.")
    parser.add_argument("--output-dir", default="output/edge_tts", help="Folder for batch MP3 files.")
    parser.add_argument("--prefix", default="", help="Prefix for generated batch filenames.")
    parser.add_argument("--manifest", help="Manifest JSON path. Defaults near the output.")
    parser.add_argument("--text-field", default=",".join(DEFAULT_TEXT_FIELDS), help="Comma-separated JSON object fields to read as sentence text.")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help=f"Microsoft Japanese voice. Default: {DEFAULT_VOICE}.")
    parser.add_argument("--rate", default=DEFAULT_RATE, help=f"Speech rate. Default: {DEFAULT_RATE.replace('%', '%%')}.")
    parser.add_argument("--pitch", default="+0Hz", help="Speech pitch adjustment. Default: +0Hz.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing MP3 files.")
    parser.add_argument("--dry-run", action="store_true", help="Only show planned filenames and write a manifest.")
    parser.add_argument("--keep-going", action="store_true", help="Continue after individual synthesis failures.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
