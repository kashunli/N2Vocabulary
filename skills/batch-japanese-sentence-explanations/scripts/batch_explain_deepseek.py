#!/usr/bin/env python3
"""Batch-generate Japanese sentence explanations with DeepSeek.

The generation path never edits the source data directly. It writes reviewable
JSON files that can be inspected and merged later with an explicit --apply.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROMPT_PATH = (
    Path(__file__).resolve().parents[1] / "references" / "explanation_prompt.md"
)
DEFAULT_CHINESE_PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "references"
    / "explanation_prompt_zh.md"
)
DEFAULT_DB_PATH = PROJECT_ROOT / "wordService" / "data" / "n2vocab.sqlite"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "output"
JSON_OUTPUT_INSTRUCTIONS = """Output requirements:
- Return valid JSON only.
- Do not return any text outside the JSON object.
- Do not add extra fields.
"""


SENTENCE_KEYS = ("sentence", "sentence_text", "text", "japanese", "ja")
USAGE_KEYS = (
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
)
KANJI_RE = re.compile(r"[\u3400-\u9fff]")
BULLET_RE = re.compile(r"^\s*[-*]\s+", re.MULTILINE)
SEPARATOR_RE = re.compile(r"(?m)^\s*---+\s*$")
PLACEHOLDER_TRANSLATION_RE = re.compile(r"^\s*\*\*自然中文翻译\*\*[：:]")
ENGLISH_FIRST_RE = re.compile(r"^\s*\*\*[A-Za-z0-9][^一-龥ぁ-んァ-ン]*[A-Za-z][^*]*\*\*")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch Japanese sentence explanations via DeepSeek API.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--source",
        choices=("json", "sqlite-main-sentences"),
        default="json",
        help="Input source. Use sqlite-main-sentences to redo weak main examples from SQLite.",
    )
    parser.add_argument("--input", help="Input JSON file for --source json.")
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help="SQLite DB path for --source sqlite-main-sentences.",
    )
    parser.add_argument("--output", help="Optional combined output JSON file.")
    parser.add_argument(
        "--output-dir",
        help="Folder for per-batch JSON files and a manifest. Defaults to a timestamped output folder.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip records with a non-empty explanation field.",
    )
    parser.add_argument(
        "--start-index", type=int, help="Only include records with index >= this value."
    )
    parser.add_argument(
        "--end-index", type=int, help="Only include records with index <= this value."
    )
    parser.add_argument("--limit", type=int, help="Maximum number of selected records.")
    parser.add_argument(
        "--batch-size", type=int, default=5, help="Sentences per DeepSeek request."
    )
    parser.add_argument(
        "--max-batch-size",
        type=int,
        default=10,
        help="Hard upper limit for --batch-size.",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=5,
        help="Maximum DeepSeek batch requests to run at once.",
    )
    parser.add_argument(
        "--model", default="deepseek-v4-flash", help="DeepSeek model id."
    )
    parser.add_argument(
        "--base-url",
        default="https://api.deepseek.com",
        help="DeepSeek OpenAI-format base URL.",
    )
    parser.add_argument(
        "--thinking",
        choices=("enabled", "disabled"),
        default="enabled",
        help="DeepSeek thinking mode. The default sends no explicit thinking level.",
    )
    parser.add_argument(
        "--temperature", type=float, default=0.2, help="Sampling temperature."
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=8192,
        help="Maximum output tokens per request. Use 0 to omit max_tokens.",
    )
    parser.add_argument(
        "--timeout", type=int, default=120, help="HTTP timeout seconds."
    )
    parser.add_argument(
        "--sleep", type=float, default=0.5, help="Seconds to sleep between batches."
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Retries when the model returns invalid JSON.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write selected records without calling the API.",
    )
    parser.add_argument(
        "--prompt-preset",
        choices=("english", "chinese"),
        default="english",
        help="Built-in explanation prompt to use when --prompt is not set.",
    )
    parser.add_argument(
        "--prompt",
        help="Markdown prompt/style contract to use as the system prompt. Overrides --prompt-preset.",
    )
    parser.add_argument(
        "--quality",
        choices=("conservative",),
        default="conservative",
        help="Quality filter for SQLite selection.",
    )
    parser.add_argument(
        "--selection",
        choices=("worst-first", "source-order"),
        default="source-order",
        help="Ordering strategy for SQLite weak-row selection.",
    )
    parser.add_argument(
        "--redo-fraction",
        type=float,
        help="Fraction of eligible SQLite weak rows to select. Use 0.5 for half.",
    )
    parser.add_argument(
        "--redo-count",
        type=int,
        help="Exact number of eligible SQLite weak rows to select; overrides --redo-fraction.",
    )
    parser.add_argument(
        "--exclude-completed",
        action="append",
        default=[],
        help="Prior completed_records.json or run_summary.json to exclude from this run.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply reviewed generated explanations to SQLite after generation/resume.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate existing batch files instead of reusing matching ones.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        for attempt in range(5):
            try:
                os.replace(tmp_path, path)
                break
            except PermissionError:
                if attempt == 4:
                    path.write_text(content, encoding="utf-8")
                    try:
                        tmp_path.unlink()
                    except OSError:
                        pass
                    break
                time.sleep(0.2 * (attempt + 1))
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_output_dir() -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    return DEFAULT_OUTPUT_ROOT / f"sentence_explanation_redo_{stamp}"


def load_prompt_style(path: Path) -> str:
    """Keep the teaching prompt editable as Markdown instead of buried in code."""
    try:
        prompt = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise SystemExit(f"Prompt file not found: {path}") from exc
    if not prompt:
        raise SystemExit(f"Prompt file is empty: {path}")
    return prompt


def resolve_prompt_path(args: argparse.Namespace) -> Path:
    if args.prompt:
        return Path(args.prompt)
    if args.prompt_preset == "chinese":
        return DEFAULT_CHINESE_PROMPT_PATH
    return DEFAULT_PROMPT_PATH


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.as_posix()}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def check_sqlite_sidecars(db_path: Path) -> None:
    wal = Path(str(db_path) + "-wal")
    if wal.exists() and wal.stat().st_size > 0:
        raise SystemExit(f"Refusing --apply because WAL has content: {wal}")


def get_windows_environment_variable(name: str) -> str | None:
    """Read persistent Windows User/Machine env vars that may not be in this shell."""
    if os.name != "nt":
        return None
    try:
        import winreg
    except ImportError:
        return None

    locations = [
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
    ]
    for root, subkey in locations:
        try:
            with winreg.OpenKey(root, subkey) as key:
                value, _value_type = winreg.QueryValueEx(key, name)
        except OSError:
            continue
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def get_api_key() -> str | None:
    return os.environ.get("DEEPSEEK_API_KEY") or get_windows_environment_variable(
        "DEEPSEEK_API_KEY"
    )


def first_sentence_value(item: dict[str, Any]) -> str:
    for key in SENTENCE_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def normalize_json_records(data: Any, args: argparse.Namespace) -> list[dict[str, Any]]:
    if isinstance(data, dict) and isinstance(data.get("sentences"), list):
        raw_items = data["sentences"]
    elif isinstance(data, list):
        raw_items = data
    else:
        raise SystemExit(
            "Input must be a JSON array or an object with a 'sentences' array."
        )

    records: list[dict[str, Any]] = []
    for position, item in enumerate(raw_items, start=1):
        if isinstance(item, str):
            record = {"index": position, "sentence": item.strip()}
        elif isinstance(item, dict):
            sentence = first_sentence_value(item)
            record = {
                "index": item.get("index", item.get("id", position)),
                "sentence": sentence,
            }
            for key in ("kanji", "reading", "verb_pattern"):
                if item.get(key):
                    record[key] = item[key]
            if "id" in item:
                record["id"] = item["id"]
            if args.skip_existing and item.get("explanation"):
                continue
            for key in (
                "entry_id",
                "position",
                "source_index",
                "unit_number",
                "translation_zh",
                "old_explanation_md",
                "quality_reasons",
            ):
                if key in item:
                    record[key] = item[key]
        else:
            continue

        if not record["sentence"]:
            continue
        if isinstance(record["index"], int):
            if args.start_index is not None and record["index"] < args.start_index:
                continue
            if args.end_index is not None and record["index"] > args.end_index:
                continue
        records.append(record)
        if args.limit is not None and len(records) >= args.limit:
            break
    return records


def bullet_count(markdown: str) -> int:
    return len(BULLET_RE.findall(markdown or ""))


def has_markdown_separator(markdown: str) -> bool:
    return bool(SEPARATOR_RE.search(markdown or ""))


def text_has_kanji(value: str) -> bool:
    return bool(KANJI_RE.search(value or ""))


def target_mentioned(explanation: str, kanji: str, reading: str) -> bool:
    candidates = []
    for value in (kanji, reading):
        value = (value or "").strip()
        if not value:
            continue
        candidates.append(value)
        for suffix in ("する", "な"):
            if value.endswith(suffix) and len(value) > len(suffix):
                candidates.append(value[: -len(suffix)])
    for candidate in candidates:
        if candidate and candidate in explanation:
            return True
    return False


def record_key(item: dict[str, Any]) -> tuple[Any, Any]:
    return (item.get("entry_id"), item.get("position", 0))


def completed_keys_from_data(data: Any) -> set[tuple[Any, Any]]:
    keys: set[tuple[Any, Any]] = set()
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("entry_id") is not None:
                keys.add(record_key(item))
    elif isinstance(data, dict):
        for field in ("completed_records", "applied_records"):
            value = data.get(field)
            if isinstance(value, list):
                keys.update(completed_keys_from_data(value))
        for field in ("completed_record_keys", "applied_record_keys"):
            value = data.get(field)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and item.get("entry_id") is not None:
                        keys.add(record_key(item))
    return keys


def load_completed_keys(paths: list[str]) -> set[tuple[Any, Any]]:
    keys: set[tuple[Any, Any]] = set()
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            raise SystemExit(f"--exclude-completed file not found: {path}")
        keys.update(completed_keys_from_data(load_json(path)))
    return keys


def explanation_length(record: dict[str, Any]) -> int:
    return len((record.get("old_explanation_md") or "").strip())


def has_severe_quality_reason(record: dict[str, Any]) -> bool:
    severe = {
        "malformed_markdown",
        "missing_separator",
        "too_few_bullets",
        "placeholder_translation_label",
        "missing_target_word",
    }
    return any(reason in severe for reason in record.get("quality_reasons", []))


def worst_first_key(record: dict[str, Any]) -> tuple[int, int, int, Any, Any]:
    reasons = record.get("quality_reasons", [])
    return (
        0 if has_severe_quality_reason(record) else 1,
        explanation_length(record),
        0 if "english_first" in reasons else 1,
        record.get("source_index", record.get("index", 0)),
        record.get("entry_id", 0),
    )


def quality_reasons_for_main_sentence(row: sqlite3.Row) -> list[str]:
    explanation = (row["old_explanation_md"] or "").strip()
    if not explanation:
        return []

    reasons: list[str] = []
    if len(explanation) < 180:
        reasons.append("length_lt_180")
    if not has_markdown_separator(explanation):
        reasons.append("missing_separator")
    if bullet_count(explanation) < 2:
        reasons.append("too_few_bullets")
    if ENGLISH_FIRST_RE.search(explanation):
        reasons.append("english_first")
    if PLACEHOLDER_TRANSLATION_RE.search(explanation):
        reasons.append("placeholder_translation_label")
    if not target_mentioned(explanation, row["kanji"] or "", row["reading"] or ""):
        reasons.append("missing_target_word")
    if explanation.count("**") % 2 != 0 or explanation.count("`") % 2 != 0:
        reasons.append("malformed_markdown")
    return reasons


def sorted_sqlite_records(records: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.selection == "worst-first":
        return sorted(records, key=worst_first_key)
    return sorted(
        records,
        key=lambda record: (
            record.get("source_index", record.get("index", 0)),
            record.get("entry_id", 0),
        ),
    )


def sqlite_redo_count(total: int, args: argparse.Namespace) -> int:
    if args.redo_count is not None:
        return min(args.redo_count, total)
    if args.redo_fraction is not None:
        return min(int(total * args.redo_fraction + 0.999999), total)
    return total


def apply_sqlite_selection_controls(records: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    completed_keys = load_completed_keys(args.exclude_completed)
    eligible = [record for record in records if record_key(record) not in completed_keys]
    ordered = sorted_sqlite_records(eligible, args)
    count = sqlite_redo_count(len(ordered), args)
    selected = ordered[:count]
    if args.limit is not None:
        selected = selected[: args.limit]
    remaining = ordered[len(selected) :]
    args._selection_summary = {
        "source": args.source,
        "quality": args.quality,
        "selection": args.selection,
        "redo_fraction": args.redo_fraction,
        "redo_count": args.redo_count,
        "limit": args.limit,
        "total_weak_records": len(records),
        "excluded_completed_count": len(records) - len(eligible),
        "eligible_records": len(eligible),
        "selected_count": len(selected),
        "remaining_count": len(remaining),
        "exclude_completed": args.exclude_completed,
    }
    args._remaining_records = remaining
    return selected


def sqlite_main_sentence_records(args: argparse.Namespace) -> list[dict[str, Any]]:
    db_path = Path(args.db)
    conn = connect_readonly(db_path)
    try:
        clauses = ["ex.position = 0", "trim(coalesce(ex.explanation_md, '')) <> ''"]
        params: list[Any] = []
        if args.start_index is not None:
            clauses.append("e.source_index >= ?")
            params.append(args.start_index)
        if args.end_index is not None:
            clauses.append("e.source_index <= ?")
            params.append(args.end_index)
        sql = f"""
            SELECT e.entry_id,
                   e.source_index,
                   e.unit_number,
                   e.kanji,
                   e.reading,
                   e.verb_pattern,
                   ex.position,
                   ex.text AS sentence,
                   ex.translation_zh,
                   ex.explanation_md AS old_explanation_md
              FROM entry_examples ex
              JOIN entries e ON e.entry_id = ex.entry_id
             WHERE {' AND '.join(clauses)}
             ORDER BY e.source_index, ex.position
        """
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    records: list[dict[str, Any]] = []
    for row in rows:
        reasons = quality_reasons_for_main_sentence(row)
        if not reasons:
            continue
        record = dict(row)
        record["index"] = row["source_index"]
        record["quality_reasons"] = reasons
        records.append(record)
    return apply_sqlite_selection_controls(records, args)


def select_records(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.source == "json":
        if not args.input:
            raise SystemExit("--input is required when --source json.")
        return normalize_json_records(load_json(Path(args.input)), args)
    return sqlite_main_sentence_records(args)


def chunks(records: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    if size <= 0:
        raise SystemExit("--batch-size must be greater than 0.")
    return [records[i : i + size] for i in range(0, len(records), size)]


def require_output_target(args: argparse.Namespace) -> None:
    if args.source == "json" and not args.output and not args.output_dir:
        raise SystemExit(
            "Provide --output-dir for monitored batch files, or --output for one combined JSON file."
        )


def output_dir_path(args: argparse.Namespace) -> Path | None:
    if args.output_dir:
        return Path(args.output_dir)
    if args.source == "sqlite-main-sentences":
        return default_output_dir()
    return None


def write_batch_artifacts(
    out_dir: Path | None,
    batch_number: int,
    batch_results: list[dict[str, Any]],
    all_results: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> None:
    if out_dir is None:
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / f"batch_{batch_number:04d}.json", batch_results)
    write_json(out_dir / "all_explanations.json", all_results)
    write_json(out_dir / "manifest.json", manifest)


def build_user_prompt(batch: list[dict[str, Any]]) -> str:
    payload = []
    for item in batch:
        payload_item = {
            "index": item["index"],
            "entry_id": item.get("entry_id", ""),
            "position": item.get("position", ""),
            "target_word": item.get("kanji", ""),
            "reading": item.get("reading", ""),
            "kanji": item.get("kanji", ""),
            "verb_pattern": item.get("verb_pattern", ""),
            "sentence": item["sentence"],
            "translation_zh": item.get("translation_zh", ""),
            "old_explanation_md": item.get("old_explanation_md", ""),
            "quality_reasons": item.get("quality_reasons", []),
        }
        payload.append(payload_item)
    return (
        "Explain the following Japanese sentences.\n"
        "Return only one valid JSON object with exactly this shape:\n"
        '{"items":[{"index":1,"explanation":"**Natural sentence translation.**\\n\\n---\\n\\n- ..."}]}\n'
        "Each explanation must use Markdown and strictly follow the system prompt. Do not add extra fields.\n\n"
        f"Sentences:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def call_deepseek(
    batch: list[dict[str, Any]],
    args: argparse.Namespace,
    api_key: str,
    prompt_style: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    url = args.base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": args.model,
        "messages": [
            {
                "role": "system",
                "content": prompt_style + "\n\n" + JSON_OUTPUT_INSTRUCTIONS,
            },
            {"role": "user", "content": build_user_prompt(batch)},
        ],
        "thinking": {"type": args.thinking},
        "response_format": {"type": "json_object"},
        "temperature": args.temperature,
    }
    if args.max_tokens:
        body["max_tokens"] = args.max_tokens
    last_json_error: json.JSONDecodeError | None = None
    attempts = max(1, args.retries + 1)
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=args.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SystemExit(f"DeepSeek HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise SystemExit(f"DeepSeek request failed: {exc}") from exc

        response_data = json.loads(raw)
        content = response_data["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            last_json_error = exc
            if attempt < attempts:
                print(
                    f"Invalid JSON from DeepSeek, retrying {attempt}/{args.retries}...",
                    flush=True,
                )
                time.sleep(args.sleep or 0.5)
                continue
            raise SystemExit(
                f"DeepSeek JSON response was invalid after {attempts} attempt(s): {exc}"
            ) from exc
        items = parsed.get("items")
        if not isinstance(items, list):
            if attempt < attempts:
                print(
                    f"DeepSeek response missing items array, retrying {attempt}/{args.retries}...",
                    flush=True,
                )
                time.sleep(args.sleep or 0.5)
                continue
            raise SystemExit(
                f"DeepSeek JSON response did not contain an items array: {content[:500]}"
            )
        return items, response_data.get("usage", {})

    raise SystemExit(f"DeepSeek JSON response was invalid: {last_json_error}")


def index_lookup(batch: list[dict[str, Any]]) -> dict[Any, dict[str, Any]]:
    lookup: dict[Any, dict[str, Any]] = {}
    for item in batch:
        lookup[item["index"]] = item
        lookup[str(item["index"])] = item
    return lookup


def normalize_output_items(
    batch: list[dict[str, Any]], generated: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    source_by_index = index_lookup(batch)
    results: list[dict[str, Any]] = []
    for item in generated:
        idx = item.get("index")
        explanation = item.get("explanation")
        source = source_by_index.get(idx, source_by_index.get(str(idx)))
        if (
            source is None
            or not isinstance(explanation, str)
            or not explanation.strip()
        ):
            continue
        out: dict[str, Any] = {
            "index": source["index"],
            "sentence": source["sentence"],
            "explanation": explanation.strip(),
        }
        for key in (
            "entry_id",
            "position",
            "source_index",
            "unit_number",
            "kanji",
            "reading",
            "verb_pattern",
            "translation_zh",
            "old_explanation_md",
            "quality_reasons",
        ):
            if key in source:
                out[key] = source[key]
        if "entry_id" in source:
            out["new_explanation_md"] = explanation.strip()
        if "id" in source:
            out["id"] = source["id"]
        results.append(out)
    return results


def load_existing_batch(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    if not isinstance(data, list):
        raise SystemExit(f"Existing batch is not a JSON array: {path}")
    return data


def batch_identity_values(items: list[dict[str, Any]]) -> list[tuple[Any, Any, Any]]:
    values = []
    for item in items:
        values.append((item.get("entry_id"), item.get("position"), item.get("index")))
    return values


def batch_matches_input(batch: list[dict[str, Any]], batch_results: list[dict[str, Any]]) -> bool:
    return batch_identity_values(batch) == batch_identity_values(batch_results)


def empty_usage() -> dict[str, int]:
    return {key: 0 for key in USAGE_KEYS}


def merge_usage(total: dict[str, int], usage: dict[str, Any]) -> None:
    for key, value in usage.items():
        if isinstance(value, int):
            total[key] = total.get(key, 0) + value


def write_generation_artifacts(
    out_dir: Path | None,
    all_results: list[dict[str, Any]],
    manifest: dict[str, Any],
    errors: list[dict[str, Any]],
    output_path: Path | None,
) -> None:
    if out_dir is not None:
        write_json(out_dir / "all_explanations.json", all_results)
        write_json(out_dir / "manifest.json", manifest)
        write_json(out_dir / "generation_errors.json", errors)
    if output_path is not None:
        write_json(output_path, all_results)


def selected_record_keys(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"entry_id": item.get("entry_id"), "position": item.get("position", 0)}
        for item in records
        if item.get("entry_id") is not None
    ]


def base_run_summary(args: argparse.Namespace, selected_records: list[dict[str, Any]]) -> dict[str, Any]:
    prompt_path = resolve_prompt_path(args)
    summary = dict(getattr(args, "_selection_summary", {}))
    summary.update(
        {
            "created_at": utc_now(),
            "db": str(Path(args.db)) if args.source == "sqlite-main-sentences" else None,
            "model": args.model,
            "thinking": args.thinking,
            "prompt_preset": args.prompt_preset,
            "prompt": str(prompt_path),
            "batch_size": args.batch_size,
            "max_batch_size": args.max_batch_size,
            "parallel": args.parallel,
            "selected_record_keys": selected_record_keys(selected_records),
            "completed_count": 0,
            "completed_record_keys": [],
            "failed_count": 0,
            "applied_count": 0,
            "skipped_rows": 0,
        }
    )
    return summary


def write_progress_files(
    out_dir: Path | None,
    selected_records: list[dict[str, Any]],
    completed_records: list[dict[str, Any]],
    remaining_records: list[dict[str, Any]],
    run_summary: dict[str, Any],
) -> None:
    if out_dir is None:
        return
    write_json(out_dir / "selected_records.json", selected_records)
    write_json(out_dir / "completed_records.json", completed_records)
    write_json(out_dir / "remaining_records.json", remaining_records)
    summary = dict(run_summary)
    summary["selected_count"] = len(selected_records)
    summary["completed_count"] = len(completed_records)
    summary["remaining_count"] = len(remaining_records)
    summary["completed_record_keys"] = selected_record_keys(completed_records)
    write_json(out_dir / "run_summary.json", summary)


def remaining_with_failed(
    selected_records: list[dict[str, Any]],
    completed_records: list[dict[str, Any]],
    base_remaining_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    completed = {record_key(item) for item in completed_records}
    failed_or_unfinished = [
        item for item in selected_records if record_key(item) not in completed
    ]
    return failed_or_unfinished + base_remaining_records


def run_one_batch(
    batch_number: int,
    batch: list[dict[str, Any]],
    batch_path: Path | None,
    args: argparse.Namespace,
    prompt_style: str,
) -> tuple[int, list[dict[str, Any]], dict[str, Any], str]:
    if batch_path is not None and batch_path.exists() and not args.force:
        batch_results = load_existing_batch(batch_path)
        if batch_matches_input(batch, batch_results):
            return batch_number, batch_results, {}, "reused"
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY was not found in the current process env, Windows User env, or Windows Machine env."
        )
    generated, usage = call_deepseek(batch, args, api_key, prompt_style)
    batch_results = normalize_output_items(batch, generated)
    if len(batch_results) != len(batch):
        raise RuntimeError(
            f"Batch {batch_number} returned {len(batch_results)} usable rows for {len(batch)} input rows."
        )
    if batch_path is not None:
        write_json(batch_path, batch_results)
    return batch_number, batch_results, usage, "generated"


def generate_records(
    args: argparse.Namespace,
    records: list[dict[str, Any]],
    out_dir: Path | None,
    output_path: Path | None,
) -> list[dict[str, Any]]:
    base_remaining_records = list(getattr(args, "_remaining_records", []))
    run_summary = base_run_summary(args, records)
    if args.dry_run:
        selected = [
            {
                **r,
                "explanation": None,
                "new_explanation_md": None,
            }
            for r in records
        ]
        remaining = list(base_remaining_records)
        if out_dir is not None:
            write_progress_files(out_dir, selected, [], remaining, run_summary)
            print(
                f"Dry run selected {len(records)} records -> {out_dir / 'selected_records.json'}"
            )
        if output_path is not None:
            write_json(output_path, selected)
            print(f"Dry run selected {len(records)} records -> {output_path}")
        return []

    prompt_path = resolve_prompt_path(args)
    prompt_style = load_prompt_style(prompt_path)
    if out_dir is not None:
        write_json(out_dir / "selected_records.json", records)

    total_usage = empty_usage()
    all_results_by_batch: dict[int, list[dict[str, Any]]] = {}
    errors: list[dict[str, Any]] = []
    batches = chunks(records, args.batch_size)
    manifest: dict[str, Any] = {
        "created_at": utc_now(),
        "source": args.source,
        "input": str(Path(args.input)) if args.input else None,
        "db": str(Path(args.db)) if args.source == "sqlite-main-sentences" else None,
        "quality": args.quality,
        "model": args.model,
        "thinking": args.thinking,
        "prompt_preset": args.prompt_preset,
        "prompt": str(prompt_path),
        "selected_records": len(records),
        "batch_size": args.batch_size,
        "max_batch_size": args.max_batch_size,
        "parallel": args.parallel,
        "completed_batches": 0,
        "completed_explanations": 0,
        "failed_batches": 0,
        "batches": [],
        "usage": total_usage,
    }
    manifest.update(getattr(args, "_selection_summary", {}))

    def batch_path(number: int) -> Path | None:
        return out_dir / f"batch_{number:04d}.json" if out_dir is not None else None

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallel) as executor:
        futures = {
            executor.submit(
                run_one_batch,
                number,
                batch,
                batch_path(number),
                args,
                prompt_style,
            ): (number, batch)
            for number, batch in enumerate(batches, start=1)
        }
        for future in concurrent.futures.as_completed(futures):
            number, batch = futures[future]
            try:
                finished_number, batch_results, usage, status = future.result()
                all_results_by_batch[finished_number] = batch_results
                merge_usage(total_usage, usage)
                print(
                    f"batch {finished_number}/{len(batches)}: {status} {len(batch_results)} rows",
                    flush=True,
                )
            except BaseException as exc:
                if isinstance(exc, KeyboardInterrupt):
                    raise
                errors.append(
                    {
                        "batch": number,
                        "entry_ids": [item.get("entry_id") for item in batch],
                        "error": str(exc),
                    }
                )
                print(f"batch {number}/{len(batches)}: failed: {exc}", flush=True)
            ordered_results: list[dict[str, Any]] = []
            for batch_number in sorted(all_results_by_batch):
                ordered_results.extend(all_results_by_batch[batch_number])
            current_remaining = remaining_with_failed(
                records, ordered_results, base_remaining_records
            )
            manifest["completed_batches"] = len(all_results_by_batch)
            manifest["completed_explanations"] = len(ordered_results)
            manifest["failed_batches"] = len(errors)
            manifest["usage"] = total_usage
            manifest["batches"] = [
                {
                    "batch": batch_number,
                    "rows": len(all_results_by_batch[batch_number]),
                    "path": str((out_dir / f"batch_{batch_number:04d}.json")) if out_dir is not None else None,
                }
                for batch_number in sorted(all_results_by_batch)
            ]
            run_summary["failed_count"] = len(current_remaining) - len(base_remaining_records)
            run_summary["usage"] = total_usage
            write_generation_artifacts(out_dir, ordered_results, manifest, errors, output_path)
            write_progress_files(
                out_dir,
                records,
                ordered_results,
                current_remaining,
                run_summary,
            )

    if errors:
        raise SystemExit(f"{len(errors)} batch(es) failed. See generation_errors.json.")
    all_results: list[dict[str, Any]] = []
    for batch_number in sorted(all_results_by_batch):
        all_results.extend(all_results_by_batch[batch_number])
    return all_results


def load_all_explanations(out_dir: Path | None, output_path: Path | None) -> list[dict[str, Any]]:
    path = output_path or (out_dir / "all_explanations.json" if out_dir is not None else None)
    if path is None:
        raise SystemExit("--apply requires --output-dir or --output with generated explanations.")
    data = load_json(path)
    if not isinstance(data, list):
        raise SystemExit(f"Generated explanations file is not a JSON array: {path}")
    return data


def apply_to_sqlite(args: argparse.Namespace, out_dir: Path, output_path: Path | None) -> None:
    if args.source != "sqlite-main-sentences":
        raise SystemExit("--apply is only supported with --source sqlite-main-sentences.")
    generated = load_all_explanations(out_dir, output_path)
    if not generated:
        raise SystemExit("No generated explanations available to apply.")

    db_path = Path(args.db)
    check_sqlite_sidecars(db_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_backup = out_dir / f"n2vocab.sqlite.before_sentence_explanation_redo_{timestamp}.bak"
    original_backup = out_dir / "original_explanations_backup.json"
    work_copy = Path(tempfile.gettempdir()) / f"n2vocab_sentence_explanation_redo_{timestamp}.sqlite"
    shutil.copy2(db_path, db_backup)
    shutil.copy2(db_path, work_copy)

    conn = sqlite3.connect(str(work_copy))
    conn.row_factory = sqlite3.Row
    original_records: list[dict[str, Any]] = []
    changed = 0
    skipped = 0
    try:
        conn.execute("BEGIN")
        for item in generated:
            entry_id = item.get("entry_id")
            position = item.get("position", 0)
            new_explanation = item.get("new_explanation_md") or item.get("explanation")
            if not isinstance(entry_id, int) or int(position) != 0 or not isinstance(new_explanation, str) or not new_explanation.strip():
                skipped += 1
                continue
            row = conn.execute(
                """
                SELECT e.source_index,
                       e.kanji,
                       e.reading,
                       ex.text AS sentence,
                       ex.explanation_md AS example_explanation_md,
                       e.explanation_md AS entry_explanation_md
                  FROM entry_examples ex
                  JOIN entries e ON e.entry_id = ex.entry_id
                 WHERE ex.entry_id = ? AND ex.position = 0
                """,
                (entry_id,),
            ).fetchone()
            if row is None:
                skipped += 1
                continue
            old_example = row["example_explanation_md"] or ""
            old_entry = row["entry_explanation_md"] or ""
            original_records.append(
                {
                    "entry_id": entry_id,
                    "position": 0,
                    "source_index": row["source_index"],
                    "kanji": row["kanji"],
                    "reading": row["reading"],
                    "sentence": row["sentence"],
                    "old_entry_examples_explanation_md": old_example,
                    "old_entries_explanation_md": old_entry,
                    "new_explanation_md": new_explanation.strip(),
                    "quality_reasons": item.get("quality_reasons", []),
                }
            )
            if old_example == new_explanation.strip() and old_entry == new_explanation.strip():
                skipped += 1
                continue
            conn.execute(
                "UPDATE entry_examples SET explanation_md = ? WHERE entry_id = ? AND position = 0",
                (new_explanation.strip(), entry_id),
            )
            conn.execute(
                "UPDATE entries SET explanation_md = ? WHERE entry_id = ?",
                (new_explanation.strip(), entry_id),
            )
            changed += 1
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    write_json(original_backup, original_records)
    shutil.copy2(work_copy, db_path)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(db_path) + suffix)
        if sidecar.exists() and sidecar.stat().st_size == 0:
            try:
                sidecar.unlink()
            except PermissionError:
                pass
    summary = {
        "applied_at": utc_now(),
        "db": str(db_path),
        "db_backup": str(db_backup),
        "original_explanations_backup": str(original_backup),
        "generated_rows": len(generated),
        "changed_rows": changed,
        "skipped_rows": skipped,
    }
    write_json(out_dir / "apply_summary.json", summary)
    run_summary_path = out_dir / "run_summary.json"
    if run_summary_path.exists():
        try:
            run_summary = load_json(run_summary_path)
        except json.JSONDecodeError:
            run_summary = {}
        if isinstance(run_summary, dict):
            run_summary.update(
                {
                    "applied_at": summary["applied_at"],
                    "applied_count": changed,
                    "changed_rows": changed,
                    "skipped_rows": skipped,
                    "db_backup": str(db_backup),
                    "original_explanations_backup": str(original_backup),
                    "apply_summary": str(out_dir / "apply_summary.json"),
                    "applied_record_keys": selected_record_keys(original_records),
                }
            )
            write_json(run_summary_path, run_summary)
    print(f"applied {changed} row updates; DB backup: {db_backup}", flush=True)


def validate_args(args: argparse.Namespace) -> None:
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be greater than 0.")
    if args.max_batch_size <= 0:
        raise SystemExit("--max-batch-size must be greater than 0.")
    if args.batch_size > args.max_batch_size:
        raise SystemExit(
            f"--batch-size {args.batch_size} exceeds --max-batch-size {args.max_batch_size}."
        )
    if args.parallel <= 0:
        raise SystemExit("--parallel must be greater than 0.")
    if args.redo_fraction is not None and not (0 < args.redo_fraction <= 1):
        raise SystemExit("--redo-fraction must be greater than 0 and less than or equal to 1.0.")
    if args.redo_count is not None and args.redo_count <= 0:
        raise SystemExit("--redo-count must be greater than 0.")
    if args.apply and args.dry_run:
        raise SystemExit("--apply cannot be used with --dry-run.")


def main() -> int:
    args = parse_args()
    validate_args(args)
    require_output_target(args)
    output_path = Path(args.output) if args.output else None
    out_dir = output_dir_path(args)
    records = select_records(args)
    print(f"selected {len(records)} record(s)", flush=True)
    existing_review_file = output_path or (
        out_dir / "all_explanations.json" if out_dir is not None else None
    )
    apply_existing_review = (
        args.apply
        and existing_review_file is not None
        and existing_review_file.exists()
        and not args.force
    )
    if apply_existing_review:
        print(f"using existing reviewed explanations: {existing_review_file}", flush=True)
    elif records or args.dry_run:
        generate_records(args, records, out_dir, output_path)
    if args.apply:
        if out_dir is None:
            raise SystemExit("--apply requires --output-dir for backup files.")
        apply_to_sqlite(args, out_dir, output_path)
    if out_dir is not None:
        print(f"Output dir: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
