"""Translate N1 sentences and structured terms into English with DeepSeek.

The workflow is resumable: selected input, each validated API batch, a
manifest, and an apply summary are retained under output/. Only blank English
translations on N1-provenance rows are selected or updated.
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "wordService" / "data" / "n2vocab.sqlite"
DEFAULT_OUTPUT = PROJECT_ROOT / "output" / "n1_english_translation"
API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-v4-flash"
JAPANESE_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")

SYSTEM_PROMPT = """You translate Japanese learning examples into concise natural English.
Return only valid JSON with exactly this shape:
{"items":[{"id":"123:4","translation_en":"..."}]}

Rules:
- Return exactly one item for every input id, in input order.
- Translate `text`; use headword, meaning, type, and category only as context.
- A sentence must be a natural complete English sentence.
- A term, compound, collocation, synonym, antonym, related word, or idiom must
  be a concise English equivalent. Preserve contrasts such as ⇔ when useful.
- Do not return Japanese text, readings, Markdown, commentary, or extra keys.
"""


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def selected_records(db_path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        sql = """
        SELECT ex.item_id, ex.position, ex.kind, COALESCE(ex.category, '') category,
               ex.text, v.kanji headword, COALESCE(v.reading, '') reading,
               COALESCE(NULLIF(be.meaning_en, ''), v.meaning_en, '') meaning_en,
               group_concat(DISTINCT p.source_index) source_indexes
        FROM item_example_sources p
        JOIN item_examples ex ON ex.item_id=p.item_id AND ex.position=p.position
        JOIN vocabulary_items v ON v.item_id=ex.item_id
        JOIN book_entries be ON be.item_id=ex.item_id AND be.book_code='N1'
        WHERE p.source_book_code='N1' AND TRIM(COALESCE(ex.translation_en, ''))=''
        GROUP BY ex.item_id, ex.position
        ORDER BY MIN(p.source_index),
                 CASE WHEN ex.kind='related_term' THEN 1 ELSE 0 END,
                 ex.position
        """
        if limit is not None:
            sql += " LIMIT ?"
            rows = conn.execute(sql, (limit,)).fetchall()
        else:
            rows = conn.execute(sql).fetchall()
    finally:
        conn.close()
    return [
        {
            "id": f"{row['item_id']}:{row['position']}",
            **dict(row),
            "source_indexes": [int(x) for x in str(row["source_indexes"]).split(",")],
        }
        for row in rows
    ]


def prompt_for(rows: list[dict[str, Any]]) -> str:
    payload = [
        {key: row[key] for key in ("id", "headword", "reading", "meaning_en", "kind", "category", "text")}
        for row in rows
    ]
    return "Translate these records:\n" + json.dumps(payload, ensure_ascii=False)


def parse_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    return json.loads(text)


def call_deepseek(rows: list[dict[str, Any]], api_key: str, args: argparse.Namespace) -> tuple[list[dict[str, str]], dict[str, Any]]:
    body = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_for(rows)},
        ],
        "temperature": 0.1,
    }
    expected_ids = [row["id"] for row in rows]
    last_error: Exception | None = None
    for attempt in range(args.retries + 1):
        request = urllib.request.Request(
            args.url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=args.timeout) as response:
                envelope = json.loads(response.read().decode("utf-8"))
            parsed = parse_content(envelope["choices"][0]["message"]["content"])
            items = parsed.get("items")
            if not isinstance(items, list) or [str(x.get("id")) for x in items] != expected_ids:
                raise ValueError("response ids do not exactly match the requested batch")
            clean = []
            for item in items:
                translation = str(item.get("translation_en") or "").strip()
                if not translation or JAPANESE_RE.search(translation):
                    raise ValueError(f"invalid English translation for {item.get('id')}")
                clean.append({"id": str(item["id"]), "translation_en": translation})
            return clean, envelope.get("usage") or {}
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < args.retries:
                time.sleep(max(args.sleep, 0.5) * (attempt + 1))
    raise RuntimeError(f"DeepSeek batch failed after retries: {last_error}")


def generate(records: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    output = Path(args.output_dir)
    write_json(output / "selected_records.json", records)
    if args.dry_run:
        return []
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is not available in the current process.")
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    batch_count = (len(records) + args.batch_size - 1) // args.batch_size
    batches: list[tuple[int, list[dict[str, Any]]]] = []
    for offset in range(0, len(records), args.batch_size):
        number = offset // args.batch_size + 1
        batches.append((number, records[offset : offset + args.batch_size]))

    def run_batch(number: int, batch: list[dict[str, Any]]) -> tuple[int, list[dict[str, str]], dict[str, Any], bool]:
        path = output / f"batch_{number:04d}.json"
        if path.exists() and not args.force:
            result = json.loads(path.read_text(encoding="utf-8"))
            if [x.get("id") for x in result] != [x["id"] for x in batch]:
                raise RuntimeError(f"cached batch does not match current selection: {path}")
            return number, result, {}, False
        else:
            result, batch_usage = call_deepseek(batch, api_key, args)
            write_json(path, result)
            return number, result, batch_usage, True

    completed: dict[int, list[dict[str, str]]] = {}
    with ThreadPoolExecutor(max_workers=args.parallel) as executor:
        futures = {executor.submit(run_batch, number, batch): number for number, batch in batches}
        for future in as_completed(futures):
            number, result, batch_usage, generated = future.result()
            completed[number] = result
            for key in usage:
                usage[key] += int(batch_usage.get(key) or 0)
            action = "generated" if generated else "reused"
            print(f"batch {number}/{batch_count}: {action} {len(result)}", flush=True)
            all_results = [item for n in sorted(completed) for item in completed[n]]
            # This progress file is useful after interruption even if later
            # batches finish before earlier ones.
            write_json(output / "completed_batches.json", {
                str(n): completed[n] for n in sorted(completed)
            })
            write_json(output / "manifest.json", {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "model": args.model,
                "selected_count": len(records),
                "completed_count": len(all_results),
                "completed_batches": sorted(completed),
                "batch_size": args.batch_size,
                "parallel": args.parallel,
                "usage": usage,
            })

    all_results = [item for n in range(1, batch_count + 1) for item in completed[n]]
    write_json(output / "all_translations.json", all_results)
    return all_results


def apply_translations(records: list[dict[str, Any]], results: list[dict[str, Any]], args: argparse.Namespace) -> None:
    by_id = {row["id"]: row for row in records}
    if set(by_id) != {row["id"] for row in results}:
        raise RuntimeError("translation result set does not match selected records")
    db_path = Path(args.db)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = Path(args.output_dir) / f"n2vocab.sqlite.before_apply_{timestamp}.bak"
    shutil.copy2(db_path, backup)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN")
        canonical_changed = legacy_changed = 0
        for result in results:
            source = by_id[result["id"]]
            translation = result["translation_en"]
            changed = conn.execute(
                """UPDATE item_examples SET translation_en=?
                   WHERE item_id=? AND position=? AND TRIM(COALESCE(translation_en,''))=''""",
                (translation, source["item_id"], source["position"]),
            ).rowcount
            canonical_changed += changed
            for source_index in source["source_indexes"]:
                legacy_changed += conn.execute(
                    """UPDATE entry_examples SET translation_en=?
                       WHERE entry_id=(SELECT entry_id FROM entries WHERE book_code='N1' AND source_index=?)
                         AND text=? AND COALESCE(category,'')=?
                         AND TRIM(COALESCE(translation_en,''))=''""",
                    (translation, source_index, source["text"], source["category"]),
                ).rowcount
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = len(conn.execute("PRAGMA foreign_key_check").fetchall())
        if integrity != "ok" or foreign_keys:
            raise RuntimeError(f"database validation failed: integrity={integrity}, fk={foreign_keys}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    write_json(Path(args.output_dir) / "apply_summary.json", {
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "backup": str(backup),
        "canonical_changed": canonical_changed,
        "legacy_changed": legacy_changed,
        "integrity_check": integrity,
        "foreign_key_check_rows": foreign_keys,
    })
    print(f"applied canonical={canonical_changed}, legacy={legacy_changed}; backup={backup}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--url", default=API_URL)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--sleep", type=float, default=0.25)
    parser.add_argument("--parallel", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be positive")
    if args.parallel <= 0:
        raise SystemExit("--parallel must be positive")
    records = selected_records(Path(args.db), args.limit)
    print(f"selected {len(records)} missing N1 translations", flush=True)
    results = generate(records, args)
    if args.apply:
        if not results:
            results = json.loads((Path(args.output_dir) / "all_translations.json").read_text(encoding="utf-8"))
        apply_translations(records, results, args)


if __name__ == "__main__":
    main()
