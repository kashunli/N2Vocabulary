#!/usr/bin/env python3
"""Fill missing English/Chinese meanings in output/n2vocab.sqlite.

This is a dated, one-time migration helper. It is intentionally kept near the
update record instead of becoming a new permanent workflow. The script writes
reviewable batch JSON first; database writes require an explicit --apply.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import shlex
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "output" / "n2vocab.sqlite"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output" / "translation_fill_2026-05-17"
DEFAULT_ENV_FILE = Path.home() / ".config" / "n2vocab" / "env"

SYSTEM_PROMPT = """You translate Japanese vocabulary headwords for JLPT learners.

Return only one valid JSON object with this exact shape:
{"items":[{"entry_id":1,"source_index":1,"meaning_en":"...","meaning_zh":"..."}]}

Rules:
- Translate the vocabulary headword, not the whole example sentence.
- Use the example sentence only to choose the right sense.
- meaning_en: concise natural English, dictionary-like, 1-3 senses separated by semicolons when useful.
- meaning_zh: concise Simplified Chinese, dictionary-like, 1-3 senses separated by semicolons when useful.
- Preserve nuance for Japanese-specific words; avoid long explanations.
- Do not include readings, Markdown, notes, or extra fields.
- If a headword includes a bracketed verb pattern, translate the base expression naturally.
"""


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Fill missing N2 vocabulary translations through Aliyun DashScope.")
    ap.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path.")
    ap.add_argument("--book", default="N2", help="Book code to process.")
    ap.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Review output folder.")
    ap.add_argument("--model", default="deepseek-v4-flash", help="Aliyun Model Studio model id.")
    ap.add_argument("--base-url", default="https://dashscope.aliyuncs.com/compatible-mode/v1", help="OpenAI-compatible base URL.")
    ap.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="Optional shell env file containing DASHSCOPE_API_KEY.")
    ap.add_argument("--batch-size", type=int, default=20, help="Records per API call.")
    ap.add_argument("--limit", type=int, help="Maximum selected missing records.")
    ap.add_argument("--start-index", type=int, help="Only include entries with source_index >= this value.")
    ap.add_argument("--end-index", type=int, help="Only include entries with source_index <= this value.")
    ap.add_argument("--temperature", type=float, default=0.1, help="Sampling temperature.")
    ap.add_argument("--timeout", type=int, default=120, help="HTTP timeout seconds.")
    ap.add_argument("--sleep", type=float, default=0.4, help="Sleep seconds between API calls.")
    ap.add_argument("--retries", type=int, default=2, help="Retries for HTTP or JSON failures.")
    ap.add_argument("--overwrite-existing", action="store_true", help="Update existing meanings too. Default only fills blanks.")
    ap.add_argument("--dry-run", action="store_true", help="Write selected_records.json only; do not call the API.")
    ap.add_argument("--apply", action="store_true", help="Apply reviewed translations to the DB after generation/resume.")
    ap.add_argument("--force", action="store_true", help="Regenerate existing batch_NNNN.json files.")
    return ap.parse_args()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_env_file(path: Path, name: str) -> str | None:
    if not path.exists():
        return None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            parts = shlex.split(line, posix=True)
        except ValueError:
            continue
        if parts and parts[0] == "export":
            parts = parts[1:]
        for part in parts:
            if part.startswith(f"{name}="):
                value = part.split("=", 1)[1].strip()
                if value:
                    return value
    return None


def get_api_key(env_file: Path) -> str:
    value = os.environ.get("DASHSCOPE_API_KEY") or parse_env_file(env_file, "DASHSCOPE_API_KEY")
    if not value:
        raise SystemExit(
            "DASHSCOPE_API_KEY is missing. Export it in this shell or store it in ~/.config/n2vocab/env."
        )
    return value


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    # On this Windows-mounted repo, normal SQLite locking can fail from WSL.
    # immutable=1 gives a stable read view for selection and validation.
    uri = f"file:{db_path.as_posix()}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def selected_records(args: argparse.Namespace) -> list[dict[str, Any]]:
    db_path = Path(args.db)
    conn = connect_readonly(db_path)
    try:
        clauses = [
            "book_code = ?",
            "(trim(coalesce(meaning_en, '')) = '' OR trim(coalesce(meaning_zh, '')) = '')",
        ]
        params: list[Any] = [args.book.upper()]
        if args.start_index is not None:
            clauses.append("source_index >= ?")
            params.append(args.start_index)
        if args.end_index is not None:
            clauses.append("source_index <= ?")
            params.append(args.end_index)
        sql = f"""
            SELECT entry_id, book_code, source_index, kanji, reading, headword_text,
                   verb_pattern, meaning_en, meaning_zh, sentence
              FROM entries
             WHERE {' AND '.join(clauses)}
             ORDER BY source_index
        """
        if args.limit is not None:
            sql += " LIMIT ?"
            params.append(args.limit)
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def chunks(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    if size <= 0:
        raise SystemExit("--batch-size must be greater than 0.")
    return [items[i : i + size] for i in range(0, len(items), size)]


def build_user_prompt(batch: list[dict[str, Any]]) -> str:
    payload = []
    for r in batch:
        payload.append({
            "entry_id": r["entry_id"],
            "source_index": r["source_index"],
            "headword": r.get("headword_text") or r.get("kanji") or "",
            "kanji": r.get("kanji") or "",
            "reading": r.get("reading") or "",
            "verb_pattern": r.get("verb_pattern") or "",
            "current_meaning_en": r.get("meaning_en") or "",
            "current_meaning_zh": r.get("meaning_zh") or "",
            "example_sentence": r.get("sentence") or "",
        })
    return "Translate these vocabulary records:\n" + json.dumps(payload, ensure_ascii=False, indent=2)


def call_aliyun(batch: list[dict[str, Any]], args: argparse.Namespace, api_key: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    url = args.base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(batch)},
        ],
        "temperature": args.temperature,
    }
    request_data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(1, max(1, args.retries + 1) + 1):
        request = urllib.request.Request(
            url,
            data=request_data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=args.timeout) as response:
                response_data = json.loads(response.read().decode("utf-8"))
            content = response_data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            items = parsed.get("items")
            if not isinstance(items, list):
                raise ValueError("response JSON does not contain an items array")
            return items, response_data.get("usage", {})
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"HTTP {exc.code}: {detail[:1000]}")
        except (TimeoutError, urllib.error.URLError, KeyError, json.JSONDecodeError, ValueError) as exc:
            last_error = exc
        if attempt <= args.retries:
            print(f"API/JSON failure; retrying {attempt}/{args.retries}: {last_error}", flush=True)
            time.sleep(max(args.sleep, 0.5))
    raise SystemExit(f"Aliyun call failed after retries: {last_error}")


def normalize_batch(batch: list[dict[str, Any]], generated: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_by_id = {r["entry_id"]: r for r in batch}
    source_by_index = {r["source_index"]: r for r in batch}
    out: list[dict[str, Any]] = []
    for item in generated:
        source = None
        for key, lookup in (("entry_id", source_by_id), ("source_index", source_by_index)):
            value = item.get(key)
            if isinstance(value, str) and value.isdigit():
                value = int(value)
            source = lookup.get(value)
            if source:
                break
        en = item.get("meaning_en")
        zh = item.get("meaning_zh")
        if not source or not isinstance(en, str) or not isinstance(zh, str):
            continue
        en = en.strip()
        zh = zh.strip()
        if not en or not zh:
            continue
        out.append({
            "entry_id": source["entry_id"],
            "book_code": source["book_code"],
            "source_index": source["source_index"],
            "kanji": source.get("kanji") or "",
            "reading": source.get("reading") or "",
            "headword_text": source.get("headword_text") or "",
            "old_meaning_en": source.get("meaning_en") or "",
            "old_meaning_zh": source.get("meaning_zh") or "",
            "meaning_en": en,
            "meaning_zh": zh,
        })
    return out


def load_existing_batch(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    if not isinstance(data, list):
        raise SystemExit(f"Existing batch is not a JSON array: {path}")
    return data


def batch_matches_input(batch: list[dict[str, Any]], batch_results: list[dict[str, Any]]) -> bool:
    expected = [int(r["entry_id"]) for r in batch]
    actual: list[int] = []
    for item in batch_results:
        value = item.get("entry_id")
        if isinstance(value, str) and value.isdigit():
            value = int(value)
        if not isinstance(value, int):
            return False
        actual.append(value)
    return actual == expected


def generate(args: argparse.Namespace, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out_dir = Path(args.output_dir)
    write_json(out_dir / "selected_records.json", records)
    if args.dry_run:
        return []

    api_key = get_api_key(Path(args.env_file))
    previous_manifest: dict[str, Any] = {}
    previous_manifest_path = out_dir / "manifest.json"
    if previous_manifest_path.exists() and not args.force:
        try:
            previous_manifest = json.loads(previous_manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous_manifest = {}
    previous_usage = previous_manifest.get("usage") if previous_manifest.get("selected_count") == len(records) else None
    all_results: list[dict[str, Any]] = []
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "db": str(Path(args.db)),
        "book": args.book.upper(),
        "model": args.model,
        "base_url": args.base_url,
        "selected_count": len(records),
        "batch_size": args.batch_size,
        "batches": [],
        "usage": previous_usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }

    for batch_number, batch in enumerate(chunks(records, args.batch_size), start=1):
        batch_path = out_dir / f"batch_{batch_number:04d}.json"
        if batch_path.exists() and not args.force:
            batch_results = load_existing_batch(batch_path)
            if batch_matches_input(batch, batch_results):
                print(f"batch {batch_number}: reused {len(batch_results)} existing rows", flush=True)
            else:
                print(f"batch {batch_number}: existing file does not match selection; regenerating", flush=True)
                generated, usage = call_aliyun(batch, args, api_key)
                batch_results = normalize_batch(batch, generated)
                if len(batch_results) != len(batch):
                    raise SystemExit(
                        f"Batch {batch_number} returned {len(batch_results)} usable rows for {len(batch)} input rows."
                    )
                write_json(batch_path, batch_results)
                for key in manifest["usage"]:
                    manifest["usage"][key] += int(usage.get(key) or 0)
                time.sleep(args.sleep)
        else:
            generated, usage = call_aliyun(batch, args, api_key)
            batch_results = normalize_batch(batch, generated)
            if len(batch_results) != len(batch):
                raise SystemExit(
                    f"Batch {batch_number} returned {len(batch_results)} usable rows for {len(batch)} input rows."
                )
            write_json(batch_path, batch_results)
            print(f"batch {batch_number}: generated {len(batch_results)} rows", flush=True)
            for key in manifest["usage"]:
                manifest["usage"][key] += int(usage.get(key) or 0)
            time.sleep(args.sleep)
        all_results.extend(batch_results)
        manifest["batches"].append({
            "batch": batch_number,
            "rows": len(batch_results),
            "path": str(batch_path.relative_to(PROJECT_ROOT)),
        })
        write_json(out_dir / "all_translations.json", all_results)
        write_json(out_dir / "manifest.json", manifest)
    return all_results


def check_sqlite_sidecars(db_path: Path) -> None:
    wal = Path(str(db_path) + "-wal")
    if wal.exists() and wal.stat().st_size > 0:
        raise SystemExit(f"Refusing --apply because WAL has content: {wal}")


def apply_to_db(args: argparse.Namespace, translations: list[dict[str, Any]]) -> None:
    if not translations:
        raise SystemExit("No translations available to apply.")
    db_path = Path(args.db)
    out_dir = Path(args.output_dir)
    check_sqlite_sidecars(db_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = out_dir / f"n2vocab.sqlite.before_translation_fill_{timestamp}.bak"
    work_copy = Path(tempfile.gettempdir()) / f"n2vocab_translation_fill_{timestamp}.sqlite"
    shutil.copy2(db_path, backup)
    shutil.copy2(db_path, work_copy)

    conn = sqlite3.connect(str(work_copy))
    try:
        conn.execute("BEGIN")
        changed = 0
        for item in translations:
            row = conn.execute(
                "SELECT meaning_en, meaning_zh FROM entries WHERE entry_id = ? AND book_code = ?",
                (item["entry_id"], item["book_code"]),
            ).fetchone()
            if not row:
                continue
            old_en, old_zh = row
            new_en = item["meaning_en"] if args.overwrite_existing or not (old_en or "").strip() else old_en
            new_zh = item["meaning_zh"] if args.overwrite_existing or not (old_zh or "").strip() else old_zh
            if new_en != old_en or new_zh != old_zh:
                conn.execute(
                    "UPDATE entries SET meaning_en = ?, meaning_zh = ? WHERE entry_id = ? AND book_code = ?",
                    (new_en, new_zh, item["entry_id"], item["book_code"]),
                )
                changed += 1
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    shutil.copy2(work_copy, db_path)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(db_path) + suffix)
        if sidecar.exists():
            try:
                sidecar.unlink()
            except PermissionError:
                if sidecar.stat().st_size != 0:
                    raise
                print(f"kept zero-byte SQLite sidecar that could not be deleted: {sidecar}", flush=True)
    summary = {
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "db": str(db_path),
        "backup": str(backup),
        "changed_rows": changed,
        "translation_rows": len(translations),
        "overwrite_existing": args.overwrite_existing,
    }
    write_json(out_dir / "apply_summary.json", summary)
    print(f"applied {changed} row updates; backup: {backup}", flush=True)


def main() -> None:
    args = parse_args()
    records = selected_records(args)
    print(f"selected {len(records)} records with missing translations", flush=True)
    translations = generate(args, records)
    if args.apply:
        if not translations:
            all_path = Path(args.output_dir) / "all_translations.json"
            translations = json.loads(all_path.read_text(encoding="utf-8"))
        apply_to_db(args, translations)


if __name__ == "__main__":
    main()
