#!/usr/bin/env python3
"""Move main sentences into entry_examples and fill example translations.

This is a dated, one-time helper. It keeps the structural row move and the
Aliyun/DeepSeek translation batches reviewable before they are applied.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import shlex
import sqlite3
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "output" / "n2vocab.sqlite"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output" / "example_translation_2026-05-17"
DEFAULT_ENV_FILE = Path.home() / ".config" / "n2vocab" / "env"

SYSTEM_PROMPT = """You translate Japanese example sentences and phrases for JLPT learners.

Return only one valid JSON object with this exact shape:
{"items":[{"entry_id":1,"position":0,"translation_en":"...","translation_zh":"..."}]}

Rules:
- Translate the example text, not the vocabulary headword.
- Use the headword and word meaning only to choose the right sense.
- translation_en: natural English. Keep it concise; full sentence if input is a sentence.
- translation_zh: natural Simplified Chinese. Keep it concise; full sentence if input is a sentence.
- For collocation patterns, braces, slashes, ellipses, and placeholders, preserve the structure when useful.
- For standalone sense markers like ① or ②, translate as "Sense 1" / "义项1".
- Do not include readings, Markdown, explanations, notes, or extra fields.
"""


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Normalize N2 example sentences and translate them.")
    ap.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path.")
    ap.add_argument("--book", default="N2", help="Book code to process.")
    ap.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Review output folder.")
    ap.add_argument("--model", default="deepseek-v4-flash", help="Aliyun Model Studio model id.")
    ap.add_argument("--base-url", default="https://dashscope.aliyuncs.com/compatible-mode/v1", help="OpenAI-compatible base URL.")
    ap.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="Optional shell env file containing DASHSCOPE_API_KEY.")
    ap.add_argument("--batch-size", type=int, default=30, help="Records per API call.")
    ap.add_argument("--limit", type=int, help="Maximum selected missing example records.")
    ap.add_argument("--temperature", type=float, default=0.1, help="Sampling temperature.")
    ap.add_argument("--timeout", type=int, default=120, help="HTTP timeout seconds.")
    ap.add_argument("--sleep", type=float, default=0.35, help="Sleep seconds between API calls.")
    ap.add_argument("--retries", type=int, default=2, help="Retries for HTTP or JSON failures.")
    ap.add_argument("--prepare-db", action="store_true", help="Move entries.sentence into entry_examples position 0.")
    ap.add_argument("--apply-translations", action="store_true", help="Apply reviewed translations to entry_examples.")
    ap.add_argument("--overwrite-existing", action="store_true", help="Update existing translations too.")
    ap.add_argument("--dry-run", action="store_true", help="Write selected_records.json only; do not call the API.")
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
        raise SystemExit("DASHSCOPE_API_KEY is missing. Export it or store it in ~/.config/n2vocab/env.")
    return value


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.as_posix()}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def check_sqlite_sidecars(db_path: Path) -> None:
    wal = Path(str(db_path) + "-wal")
    if wal.exists() and wal.stat().st_size > 0:
        raise SystemExit(f"Refusing to write because WAL has content: {wal}")


def copy_back(work_copy: Path, db_path: Path) -> None:
    shutil.copy2(work_copy, db_path)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(db_path) + suffix)
        if sidecar.exists():
            try:
                sidecar.unlink()
            except PermissionError:
                # On the Windows-mounted workspace, old -wal/-shm sidecars can
                # remain locked even after the SQLite file itself has been
                # replaced. They are not the source of truth for this copy-back.
                print(f"kept locked SQLite sidecar that could not be deleted: {sidecar}", flush=True)


def require_columns(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(entry_examples)")}
    needed = {"translation_en", "translation_zh", "explanation_md", "audio_clip"}
    missing = sorted(needed - cols)
    if missing:
        raise SystemExit(f"entry_examples is missing columns: {', '.join(missing)}. Run python db/migrate.py first.")


def prepare_db(args: argparse.Namespace) -> None:
    db_path = Path(args.db)
    out_dir = Path(args.output_dir)
    check_sqlite_sidecars(db_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = out_dir / f"n2vocab.sqlite.before_example_normalize_{timestamp}.bak"
    work_copy = Path(tempfile.gettempdir()) / f"n2vocab_example_normalize_{timestamp}.sqlite"
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db_path, backup)
    shutil.copy2(db_path, work_copy)

    conn = sqlite3.connect(str(work_copy))
    conn.row_factory = sqlite3.Row
    try:
        require_columns(conn)
        already = conn.execute(
            """
            SELECT count(*)
              FROM entry_examples x
              JOIN entries e ON e.entry_id = x.entry_id
             WHERE x.position = 0
               AND trim(coalesce(e.sentence, '')) <> ''
               AND x.text = e.sentence
            """
        ).fetchone()[0]
        expected = conn.execute(
            "SELECT count(*) FROM entries WHERE trim(coalesce(sentence, '')) <> ''"
        ).fetchone()[0]
        if already == expected and expected > 0:
            summary = {
                "prepared_at": datetime.now(timezone.utc).isoformat(),
                "db": str(db_path),
                "backup": str(backup),
                "status": "already_prepared",
                "main_sentence_rows": already,
            }
            write_json(out_dir / "prepare_summary.json", summary)
            print(f"entry_examples already has {already} main sentence rows; left DB unchanged", flush=True)
            return

        old_examples = conn.execute("SELECT count(*) FROM entry_examples").fetchone()[0]
        main_sentences = expected
        conn.execute("BEGIN")
        # SQLite checks the composite primary key row by row, so use a large
        # temporary offset before settling old examples at position + 1.
        conn.execute("UPDATE entry_examples SET position = position + 100000")
        conn.execute("UPDATE entry_examples SET position = position - 99999")
        conn.execute(
            """
            INSERT INTO entry_examples (
              entry_id, position, text, translation_en, translation_zh,
              explanation_md, audio_clip
            )
            SELECT entry_id, 0, sentence, NULL, NULL, explanation_md, sentence_clip
              FROM entries
             WHERE trim(coalesce(sentence, '')) <> ''
            """
        )
        conn.execute("COMMIT")

        new_examples = conn.execute("SELECT count(*) FROM entry_examples").fetchone()[0]
        duplicate_positions = conn.execute(
            """
            SELECT count(*)
              FROM (
                SELECT entry_id, position, count(*) c
                  FROM entry_examples
                 GROUP BY entry_id, position
                HAVING c > 1
              )
            """
        ).fetchone()[0]
        summary = {
            "prepared_at": datetime.now(timezone.utc).isoformat(),
            "db": str(db_path),
            "backup": str(backup),
            "old_example_rows": old_examples,
            "main_sentence_rows_inserted": main_sentences,
            "new_example_rows": new_examples,
            "duplicate_entry_positions": duplicate_positions,
        }
        write_json(out_dir / "prepare_summary.json", summary)
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    copy_back(work_copy, db_path)
    print(f"prepared entry_examples; inserted {main_sentences} main sentence rows; backup: {backup}", flush=True)


def selected_records(args: argparse.Namespace) -> list[dict[str, Any]]:
    conn = connect_readonly(Path(args.db))
    try:
        require_columns(conn)
        clauses = [
            "e.book_code = ?",
            "trim(coalesce(x.text, '')) <> ''",
        ]
        if not args.overwrite_existing:
            clauses.append("(trim(coalesce(x.translation_en, '')) = '' OR trim(coalesce(x.translation_zh, '')) = '')")
        params: list[Any] = [args.book.upper()]
        sql = f"""
            SELECT e.entry_id, e.book_code, e.source_index, e.kanji, e.reading,
                   e.headword_text, e.meaning_en AS word_meaning_en,
                   e.meaning_zh AS word_meaning_zh,
                   x.position, x.text, x.translation_en, x.translation_zh
              FROM entry_examples x
              JOIN entries e ON e.entry_id = x.entry_id
             WHERE {' AND '.join(clauses)}
             ORDER BY e.source_index, x.position
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
            "position": r["position"],
            "headword": r.get("headword_text") or r.get("kanji") or "",
            "reading": r.get("reading") or "",
            "word_meaning_en": r.get("word_meaning_en") or "",
            "word_meaning_zh": r.get("word_meaning_zh") or "",
            "example_text": r.get("text") or "",
        })
    return "Translate these example records:\n" + json.dumps(payload, ensure_ascii=False, indent=2)


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
    source_by_key = {(int(r["entry_id"]), int(r["position"])): r for r in batch}
    out: list[dict[str, Any]] = []
    for item in generated:
        entry_id = item.get("entry_id")
        position = item.get("position")
        if isinstance(entry_id, str) and entry_id.isdigit():
            entry_id = int(entry_id)
        if isinstance(position, str) and position.isdigit():
            position = int(position)
        source = source_by_key.get((entry_id, position))
        en = item.get("translation_en")
        zh = item.get("translation_zh")
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
            "position": source["position"],
            "kanji": source.get("kanji") or "",
            "reading": source.get("reading") or "",
            "text": source.get("text") or "",
            "old_translation_en": source.get("translation_en") or "",
            "old_translation_zh": source.get("translation_zh") or "",
            "translation_en": en,
            "translation_zh": zh,
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
    expected = [(int(r["entry_id"]), int(r["position"])) for r in batch]
    actual: list[tuple[int, int]] = []
    for item in batch_results:
        entry_id = item.get("entry_id")
        position = item.get("position")
        if isinstance(entry_id, str) and entry_id.isdigit():
            entry_id = int(entry_id)
        if isinstance(position, str) and position.isdigit():
            position = int(position)
        if not isinstance(entry_id, int) or not isinstance(position, int):
            return False
        actual.append((entry_id, position))
    return actual == expected


def generate_complete_batch(
    batch: list[dict[str, Any]],
    args: argparse.Namespace,
    api_key: str,
    batch_number: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    last_count = 0
    for attempt in range(1, max(1, args.retries + 1) + 1):
        generated, usage = call_aliyun(batch, args, api_key)
        batch_results = normalize_batch(batch, generated)
        if len(batch_results) == len(batch):
            return batch_results, usage
        last_count = len(batch_results)
        if attempt <= args.retries:
            print(
                f"batch {batch_number}: got {last_count}/{len(batch)} usable rows; retrying {attempt}/{args.retries}",
                flush=True,
            )
            time.sleep(max(args.sleep, 0.5))
    raise SystemExit(f"Batch {batch_number} returned {last_count} usable rows for {len(batch)} input rows.")


def generate(args: argparse.Namespace, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out_dir = Path(args.output_dir)
    if args.dry_run and not records and (out_dir / "selected_records.json").exists():
        write_json(out_dir / "selected_records_after_apply.json", records)
        return []
    write_json(out_dir / "selected_records.json", records)
    if args.dry_run:
        return []

    api_key = get_api_key(Path(args.env_file))
    previous_manifest: dict[str, Any] = {}
    manifest_path = out_dir / "manifest.json"
    if manifest_path.exists() and not args.force:
        try:
            previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous_manifest = {}
    previous_usage = (
        previous_manifest.get("usage")
        if previous_manifest.get("selected_count") == len(records)
        else None
    )
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
                batch_results, usage = generate_complete_batch(batch, args, api_key, batch_number)
                write_json(batch_path, batch_results)
                for key in manifest["usage"]:
                    manifest["usage"][key] += int(usage.get(key) or 0)
                time.sleep(args.sleep)
        else:
            batch_results, usage = generate_complete_batch(batch, args, api_key, batch_number)
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


def apply_translations(args: argparse.Namespace, translations: list[dict[str, Any]]) -> None:
    if not translations:
        raise SystemExit("No translations available to apply.")
    db_path = Path(args.db)
    out_dir = Path(args.output_dir)
    check_sqlite_sidecars(db_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = out_dir / f"n2vocab.sqlite.before_example_translation_apply_{timestamp}.bak"
    work_copy = Path(tempfile.gettempdir()) / f"n2vocab_example_translation_apply_{timestamp}.sqlite"
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db_path, backup)
    shutil.copy2(db_path, work_copy)

    conn = sqlite3.connect(str(work_copy))
    try:
        require_columns(conn)
        conn.execute("BEGIN")
        changed = 0
        for item in translations:
            row = conn.execute(
                """
                SELECT x.translation_en, x.translation_zh
                  FROM entry_examples x
                  JOIN entries e ON e.entry_id = x.entry_id
                 WHERE x.entry_id = ? AND x.position = ? AND e.book_code = ?
                """,
                (item["entry_id"], item["position"], item["book_code"]),
            ).fetchone()
            if not row:
                continue
            old_en, old_zh = row
            new_en = item["translation_en"] if args.overwrite_existing or not (old_en or "").strip() else old_en
            new_zh = item["translation_zh"] if args.overwrite_existing or not (old_zh or "").strip() else old_zh
            if new_en != old_en or new_zh != old_zh:
                conn.execute(
                    """
                    UPDATE entry_examples
                       SET translation_en = ?, translation_zh = ?
                     WHERE entry_id = ? AND position = ?
                    """,
                    (new_en, new_zh, item["entry_id"], item["position"]),
                )
                changed += 1
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    copy_back(work_copy, db_path)
    summary = {
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "db": str(db_path),
        "backup": str(backup),
        "changed_rows": changed,
        "translation_rows": len(translations),
        "overwrite_existing": args.overwrite_existing,
    }
    write_json(out_dir / "apply_summary.json", summary)
    print(f"applied {changed} example translations; backup: {backup}", flush=True)


def main() -> None:
    args = parse_args()
    if args.prepare_db:
        prepare_db(args)
    records = selected_records(args)
    print(f"selected {len(records)} entry_examples rows with missing translations", flush=True)
    translations = generate(args, records)
    if args.apply_translations:
        if not translations:
            all_path = Path(args.output_dir) / "all_translations.json"
            translations = json.loads(all_path.read_text(encoding="utf-8"))
        apply_translations(args, translations)


if __name__ == "__main__":
    main()
