"""Add English word meanings to the N2_1500 book with DeepSeek.

The script intentionally updates only ``entries.meaning_en`` and the matching
``meaning_en`` field in ``data/n2_must_1500_vocab.json``. Related forms and
example-sentence tables are left untouched because this workflow is for the
book's headwords only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import winreg
except ImportError:  # pragma: no cover - non-Windows fallback
    winreg = None


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JSON = PROJECT_ROOT / "data" / "n2_must_1500_vocab.json"
DEFAULT_DB = PROJECT_ROOT / "wordService" / "data" / "n2vocab.sqlite"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output" / "n2_1500_english_meanings_2026-06-25"

BOOK_CODE = "N2_1500"
EXPECTED_ENTRY_COUNT = 1488
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-v4-flash"
MEANING_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


def read_api_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    if winreg is None:
        return ""
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(root, r"Environment") as handle:
                value, _ = winreg.QueryValueEx(handle, "DEEPSEEK_API_KEY")
                if str(value).strip():
                    return str(value).strip()
        except OSError:
            continue
    return ""


def load_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("book_code") != BOOK_CODE:
        raise ValueError(f"expected book_code {BOOK_CODE!r}, found {payload.get('book_code')!r}")
    entries = payload.get("entries")
    if not isinstance(entries, list) or len(entries) != EXPECTED_ENTRY_COUNT:
        raise ValueError(f"expected {EXPECTED_ENTRY_COUNT} entries, found {len(entries or [])}")
    return payload


def selected_entries(payload: dict[str, Any], args: argparse.Namespace) -> list[dict[str, Any]]:
    rows = []
    for entry in payload["entries"]:
        source_index = int(entry["source_index"])
        if args.start_index and source_index < args.start_index:
            continue
        if args.end_index and source_index > args.end_index:
            continue
        if args.skip_existing and str(entry.get("meaning_en", "")).strip():
            continue
        rows.append(entry)
    if args.limit is not None:
        rows = rows[: args.limit]
    return rows


def prompt_for_batch(rows: list[dict[str, Any]]) -> str:
    compact_rows = [
        {
            "source_index": int(row["source_index"]),
            "headword": row["headword"],
            "reading": row.get("reading", ""),
            "part_of_speech": row["part_of_speech"],
            "meaning_zh": row["meaning_zh"],
        }
        for row in rows
    ]
    return (
        "You are enriching a JLPT N2 vocabulary book. Return JSON only.\n"
        "For each item, translate the headword meaning into concise natural English.\n"
        "Translate only the word meaning. Do not translate related forms, example sentences, "
        "grammar terms, accents, or source notes.\n"
        "Keep each meaning dictionary-style, usually 1 to 6 short English glosses separated "
        "by semicolons. Do not include Japanese, Chinese, examples, numbering, markdown, or notes.\n"
        "Return exactly this shape: {\"meanings\":[{\"source_index\":1,\"meaning_en\":\"...\"}]}.\n\n"
        f"Items:\n{json.dumps(compact_rows, ensure_ascii=False)}"
    )


def call_deepseek(api_key: str, rows: list[dict[str, Any]], timeout: int, retries: int) -> dict[str, Any]:
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You produce strict JSON for Japanese vocabulary data enrichment.",
            },
            {"role": "user", "content": prompt_for_batch(rows)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        DEEPSEEK_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
            data = json.loads(raw)
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except (KeyError, json.JSONDecodeError, urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(min(2 * attempt, 10))
    raise RuntimeError(f"DeepSeek request failed after {retries} attempts: {last_error}")


def validate_batch_result(rows: list[dict[str, Any]], result: dict[str, Any]) -> dict[int, str]:
    expected = {int(row["source_index"]) for row in rows}
    meanings = result.get("meanings")
    if not isinstance(meanings, list):
        raise ValueError("response does not contain a meanings list")

    parsed: dict[int, str] = {}
    for item in meanings:
        source_index = int(item["source_index"])
        meaning = str(item["meaning_en"]).strip()
        if source_index not in expected:
            raise ValueError(f"unexpected source_index {source_index}")
        validate_meaning(source_index, meaning)
        parsed[source_index] = meaning

    missing = sorted(expected - set(parsed))
    if missing:
        raise ValueError(f"missing meanings for source indexes: {missing[:10]}")
    return parsed


def validate_meaning(source_index: int, meaning: str) -> None:
    if not meaning:
        raise ValueError(f"blank meaning for source_index {source_index}")
    if "\n" in meaning:
        raise ValueError(f"multiline meaning for source_index {source_index}")
    if len(meaning) > 180:
        raise ValueError(f"meaning too long for source_index {source_index}: {meaning!r}")
    if MEANING_CJK_RE.search(meaning):
        raise ValueError(f"meaning contains Japanese or Chinese for source_index {source_index}: {meaning!r}")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def generate_meanings(rows: list[dict[str, Any]], args: argparse.Namespace) -> dict[int, str]:
    api_key = read_api_key()
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")

    all_meanings: dict[int, str] = {}
    errors: list[dict[str, Any]] = []
    batches = [rows[index : index + args.batch_size] for index in range(0, len(rows), args.batch_size)]

    for batch_number, batch_rows in enumerate(batches, 1):
        batch_path = args.output_dir / f"batch_{batch_number:04d}.json"
        if batch_path.exists() and not args.force:
            batch_payload = json.loads(batch_path.read_text(encoding="utf-8"))
            parsed = {int(item["source_index"]): str(item["meaning_en"]).strip() for item in batch_payload["meanings"]}
        else:
            print(f"Generating batch {batch_number}/{len(batches)} ({len(batch_rows)} words)", flush=True)
            try:
                result = call_deepseek(api_key, batch_rows, args.timeout, args.retries)
                parsed = validate_batch_result(batch_rows, result)
                write_json(
                    batch_path,
                    {
                        "book_code": BOOK_CODE,
                        "batch_number": batch_number,
                        "generated_at": datetime.now().isoformat(timespec="seconds"),
                        "meanings": [
                            {"source_index": source_index, "meaning_en": parsed[source_index]}
                            for source_index in sorted(parsed)
                        ],
                    },
                )
            except Exception as exc:
                errors.append(
                    {
                        "batch_number": batch_number,
                        "source_indexes": [int(row["source_index"]) for row in batch_rows],
                        "error": str(exc),
                    }
                )
                print(f"Batch {batch_number} failed: {exc}", flush=True)
                continue
        all_meanings.update(parsed)

    if errors:
        write_json(args.output_dir / "generation_errors.json", errors)
    return all_meanings


def validate_complete_meanings(payload: dict[str, Any], meanings: dict[int, str]) -> None:
    expected = {int(row["source_index"]) for row in payload["entries"]}
    missing = sorted(expected - set(meanings))
    extra = sorted(set(meanings) - expected)
    if missing or extra:
        raise ValueError(f"meaning coverage mismatch: {len(missing)} missing, {len(extra)} extra")
    for source_index, meaning in meanings.items():
        validate_meaning(source_index, meaning)


def apply_meanings(json_path: Path, db_path: Path, payload: dict[str, Any], meanings: dict[int, str], output_dir: Path) -> None:
    validate_complete_meanings(payload, meanings)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_backup = output_dir / f"{json_path.name}.backup_before_english_meanings_{stamp}"
    db_backup = output_dir / f"{db_path.name}.backup_before_english_meanings_{stamp}"
    shutil.copy2(json_path, json_backup)
    shutil.copy2(db_path, db_backup)

    for entry in payload["entries"]:
        entry["meaning_en"] = meanings[int(entry["source_index"])]
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    connection = sqlite3.connect(db_path, timeout=30)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("BEGIN")
        for source_index, meaning in sorted(meanings.items()):
            connection.execute(
                "UPDATE entries SET meaning_en=? WHERE book_code=? AND source_index=?",
                (meaning, BOOK_CODE, source_index),
            )
        db_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM entries
            WHERE book_code=? AND NULLIF(TRIM(meaning_en), '') IS NOT NULL
            """,
            (BOOK_CODE,),
        ).fetchone()[0]
        if db_count != EXPECTED_ENTRY_COUNT:
            raise RuntimeError(f"SQLite update incomplete: {db_count}/{EXPECTED_ENTRY_COUNT} rows have meaning_en")
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()

    write_json(
        output_dir / "apply_summary.json",
        {
            "book_code": BOOK_CODE,
            "entries_updated": len(meanings),
            "json": str(json_path),
            "db": str(db_path),
            "json_backup": str(json_backup),
            "db_backup": str(db_backup),
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=40)
    parser.add_argument("--start-index", type=int)
    parser.add_argument("--end-index", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="regenerate existing batch files")
    parser.add_argument("--apply", action="store_true", help="write meanings to JSON and SQLite")
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()

    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    payload = load_payload(args.json)
    rows = selected_entries(payload, args)
    write_json(args.output_dir / "selected_records.json", rows)

    if args.dry_run:
        meanings = {
            int(row["source_index"]): str(row.get("meaning_en", "")).strip()
            for row in payload["entries"]
            if str(row.get("meaning_en", "")).strip()
        }
    else:
        meanings = generate_meanings(rows, args)

    write_json(
        args.output_dir / "all_meanings.json",
        {
            "book_code": BOOK_CODE,
            "generated_or_loaded": len(meanings),
            "meanings": [
                {"source_index": source_index, "meaning_en": meanings[source_index]}
                for source_index in sorted(meanings)
            ],
        },
    )
    write_json(
        args.output_dir / "run_summary.json",
        {
            "book_code": BOOK_CODE,
            "selected_entries": len(rows),
            "meanings_available": len(meanings),
            "dry_run": args.dry_run,
            "apply": args.apply,
            "output_dir": str(args.output_dir),
        },
    )

    if args.apply:
        apply_meanings(args.json, args.db, payload, meanings, args.output_dir)
    print(
        json.dumps(
            {
                "book_code": BOOK_CODE,
                "selected_entries": len(rows),
                "meanings_available": len(meanings),
                "applied": args.apply,
                "output_dir": str(args.output_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
