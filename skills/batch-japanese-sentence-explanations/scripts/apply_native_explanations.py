#!/usr/bin/env python3
"""Validate and apply native ChatGPT sentence explanations to the canonical DB.

The text in the input file is produced by the native ChatGPT model, not by
this script.  This helper owns the safety boundary between that generated
JSON and SQLite: it proves that every record still points at the expected N1
sentence, refuses non-empty explanations unless explicitly told to overwrite,
creates a timestamped database backup, and validates the committed result.

Input is a JSON array.  Each record must contain:

    {
      "source_index": 1,
      "item_id": 123,
      "position": 0,
      "sentence": "Japanese sentence。",
      "new_explanation_md": "**Natural English translation.**\\n\\n---\\n\\n- ..."
    }

``explanation_md`` and ``explanation`` are accepted as aliases for
``new_explanation_md`` so a reviewed batch can be copied from older workflow
artifacts without a hand-editing step.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_DB = Path(__file__).resolve().parents[3] / "wordService" / "data" / "n2vocab.sqlite"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[3] / "output" / "native_n1_sentence_explanations"


class NativeExplanationError(RuntimeError):
    """Raised when a generated batch is unsafe or does not match the DB."""


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise NativeExplanationError(f"input JSON does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise NativeExplanationError(f"input JSON is invalid: {path}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise NativeExplanationError(f"{field} must be a positive integer: {value!r}")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise NativeExplanationError(f"{field} must be a non-negative integer: {value!r}")
    return value


def validate_markdown(value: Any, record_number: int) -> str:
    if not isinstance(value, str):
        raise NativeExplanationError(
            f"record {record_number}: explanation must be a string"
        )
    explanation = value.strip()
    if not explanation:
        raise NativeExplanationError(f"record {record_number}: explanation is blank")
    if "\x00" in explanation:
        raise NativeExplanationError(f"record {record_number}: explanation contains NUL")
    if len(explanation) > 20_000:
        raise NativeExplanationError(
            f"record {record_number}: explanation is implausibly long ({len(explanation)} chars)"
        )

    nonblank = [line.strip() for line in explanation.splitlines() if line.strip()]
    if not nonblank[0].startswith("**") or nonblank[0].count("**") < 2:
        raise NativeExplanationError(
            f"record {record_number}: first nonblank line must be a bold English translation"
        )
    if not any(line == "---" for line in nonblank):
        raise NativeExplanationError(
            f"record {record_number}: explanation must contain a Markdown separator (---)"
        )
    separator = next(i for i, line in enumerate(nonblank) if line == "---")
    bullets = [line for line in nonblank[separator + 1 :] if line.startswith("-")]
    if len(bullets) < 2:
        raise NativeExplanationError(
            f"record {record_number}: explanation needs at least two sentence-anchored bullets"
        )
    # Provenance is stored in item_source_notes.  Reject the most common old
    # form here so a native batch cannot silently put book citations back into
    # the learner-facing explanation field.
    if "**Source:**" in explanation or "N1語彙トレーニング" in explanation:
        raise NativeExplanationError(
            f"record {record_number}: source provenance must not be copied into explanation_md"
        )
    return explanation


def normalise_records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise NativeExplanationError("input JSON must be a non-empty array")

    records: list[dict[str, Any]] = []
    source_indexes: set[int] = set()
    keys: set[tuple[int, int]] = set()
    for number, raw in enumerate(value, start=1):
        if not isinstance(raw, dict):
            raise NativeExplanationError(f"record {number}: expected an object")
        source_index = _positive_int(raw.get("source_index"), f"record {number}.source_index")
        item_id = _positive_int(raw.get("item_id"), f"record {number}.item_id")
        position = _nonnegative_int(raw.get("position"), f"record {number}.position")
        sentence = raw.get("sentence")
        if not isinstance(sentence, str) or not sentence.strip():
            raise NativeExplanationError(f"record {number}: sentence must be nonblank text")
        explanation_value = raw.get("new_explanation_md")
        if explanation_value is None:
            explanation_value = raw.get("explanation_md")
        if explanation_value is None:
            explanation_value = raw.get("explanation")
        explanation = validate_markdown(explanation_value, number)

        key = (item_id, position)
        if source_index in source_indexes:
            raise NativeExplanationError(f"duplicate source_index in input: {source_index}")
        if key in keys:
            raise NativeExplanationError(f"duplicate item_id/position in input: {key}")
        source_indexes.add(source_index)
        keys.add(key)
        records.append(
            {
                "source_index": source_index,
                "item_id": item_id,
                "position": position,
                "sentence": sentence.strip(),
                "new_explanation_md": explanation,
            }
        )
    return records


def check_sidecars(db_path: Path) -> None:
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = Path(str(db_path) + suffix)
        if sidecar.exists() and sidecar.stat().st_size:
            raise NativeExplanationError(
                f"refusing to write while SQLite sidecar has content: {sidecar}"
            )


def fetch_targets(
    conn: sqlite3.Connection, records: list[dict[str, Any]], book_code: str
) -> dict[tuple[int, int], sqlite3.Row]:
    placeholders = ",".join("?" for _ in records)
    source_indexes = [record["source_index"] for record in records]
    rows = conn.execute(
        f"""
        SELECT be.source_index, be.item_id, be.sentence AS book_sentence,
               ex.position, ex.kind, ex.text AS example_text,
               ex.explanation_md
          FROM book_entries be
          JOIN item_examples ex ON ex.item_id = be.item_id
                               AND trim(ex.text) = trim(be.sentence)
         WHERE be.book_code = ?
           AND be.source_index IN ({placeholders})
        """,
        [book_code, *source_indexes],
    ).fetchall()
    by_key: dict[tuple[int, int], sqlite3.Row] = {}
    for row in rows:
        key = (int(row["item_id"]), int(row["position"]))
        if key in by_key:
            raise NativeExplanationError(
                f"database has multiple exact example matches for item_id/position {key}"
            )
        by_key[key] = row
    return by_key


def validate_targets(
    conn: sqlite3.Connection,
    records: list[dict[str, Any]],
    book_code: str,
    overwrite: bool,
) -> list[dict[str, Any]]:
    targets = fetch_targets(conn, records, book_code)
    original: list[dict[str, Any]] = []
    for record in records:
        key = (record["item_id"], record["position"])
        row = targets.get(key)
        if row is None:
            raise NativeExplanationError(
                "no exact canonical sentence row for "
                f"source_index={record['source_index']} item_id/position={key}"
            )
        if int(row["source_index"]) != record["source_index"]:
            raise NativeExplanationError(
                "item_id/position resolves to another source index: "
                f"input={record['source_index']} db={row['source_index']} key={key}"
            )
        if row["book_sentence"].strip() != record["sentence"] or row["example_text"].strip() != record["sentence"]:
            raise NativeExplanationError(
                f"sentence mismatch at source_index={record['source_index']}"
            )
        old = (row["explanation_md"] or "").strip()
        if old and not overwrite:
            raise NativeExplanationError(
                "refusing to overwrite existing explanation at "
                f"source_index={record['source_index']}; pass --overwrite explicitly"
            )
        original.append(
            {
                **record,
                "book_code": book_code,
                "kind": row["kind"],
                "old_explanation_md": old,
            }
        )
    return original


def apply_records(
    db_path: Path,
    records: list[dict[str, Any]],
    output_dir: Path,
    book_code: str,
    overwrite: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    db_path = db_path.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if not db_path.is_file():
        raise NativeExplanationError(f"SQLite database does not exist: {db_path}")
    check_sidecars(db_path)

    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        original = validate_targets(conn, records, book_code, overwrite)
        if dry_run:
            return {
                "dry_run": True,
                "db": str(db_path),
                "book_code": book_code,
                "input_rows": len(records),
                "would_change": sum(1 for row in original if row["old_explanation_md"] != row["new_explanation_md"]),
            }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = output_dir / f"{db_path.stem}.before_native_explanations_{timestamp}.bak"
        original_backup = output_dir / f"original_explanations_{timestamp}.json"
        shutil.copy2(db_path, backup)
        try:
            conn.execute("BEGIN IMMEDIATE")
            changed = 0
            for row in original:
                changed += conn.execute(
                    """
                    UPDATE item_examples
                       SET explanation_md = ?
                     WHERE item_id = ? AND position = ?
                    """,
                    (row["new_explanation_md"], row["item_id"], row["position"]),
                ).rowcount
            if changed != len(original):
                raise NativeExplanationError(
                    f"expected {len(original)} item_examples updates, got {changed}"
                )
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
            if integrity != "ok" or foreign_keys:
                raise NativeExplanationError(
                    f"database validation failed: integrity={integrity}, foreign_keys={len(foreign_keys)}"
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        write_json(original_backup, original)
        summary = {
            "applied_at": datetime.now(timezone.utc).isoformat(),
            "db": str(db_path),
            "book_code": book_code,
            "input_rows": len(records),
            "changed_rows": changed,
            "backup": str(backup),
            "original_explanations_backup": str(original_backup),
            "integrity_check": integrity,
            "foreign_key_check_rows": len(foreign_keys),
        }
        write_json(output_dir / f"apply_summary_{timestamp}.json", summary)
        return summary
    finally:
        conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="native-generated JSON array")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--book-code", default="N1")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        records = normalise_records(load_json(args.input))
        summary = apply_records(
            args.db,
            records,
            args.output_dir,
            args.book_code,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
        )
    except NativeExplanationError as exc:
        print(f"error: {exc}")
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
