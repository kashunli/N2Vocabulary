#!/usr/bin/env python3
"""Extract related forms from N2_1500 entries into entry_examples.

Parses the ``### Related forms`` section of the markdown, which contains lines like::

    - 連 跡を追う（追赶；效仿）
    - 合 足跡 [あしあと]（足迹）
    - 対 黒字 [くろじ]（盈余）
    - 類 間違 [まちが]い（错误）
    - 慣 穴があれば入りたい（想找个地洞钻进去）

Each line becomes one or more ``entry_examples`` rows. The source marker is kept
as the row category (for example, ``合``), bracketed readings are preserved in
``entry_examples.reading``, and the related-forms markdown section is removed
from the word-level explanation.

Usage::

    python tools/extract_related_forms.py --apply [--db PATH]

Default DB is ``wordService/data/n2vocab.sqlite``.
"""

import argparse
import json
import re
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "wordService" / "data" / "n2vocab.sqlite"
DEFAULT_JSON = PROJECT_ROOT / "data" / "n2_must_1500_vocab.json"

RELATED_MARKERS = ("連", "合", "対", "類", "慣")
OLD_CATEGORY_VALUES = ("collocation", "compound", "antonym", "synonym", "idiom")

# Lines under ### Related forms look like:  "- 連 跡を追う（追赶；效仿）"
LINE_RE = re.compile(r"^- ([連合対類慣]) (.+)$")

# Reading annotations in brackets: 足跡 [あしあと] -> text=足跡, reading=あしあと
READING_RE = re.compile(r"\s*\[([^\]]+)\]\s*")


@dataclass(frozen=True)
class RelatedExample:
    text: str
    reading: str
    translation_zh: str
    category: str


def _split_reading(text: str) -> tuple[str, str]:
    """Return display text plus any bracket readings found in source order."""
    readings: list[str] = []

    def remember(match: re.Match[str]) -> str:
        readings.append(match.group(1).strip())
        return ""

    cleaned = READING_RE.sub(remember, text).strip()
    # Spaces in this source are usually PDF layout artifacts around bracketed
    # readings, e.g. ``悪 [あく] 影響`` should become ``悪影響``.
    cleaned = re.sub(r"\s+", "", cleaned)
    return cleaned, " / ".join(reading for reading in readings if reading)


def parse_related_line(line: str) -> list[RelatedExample]:
    """Parse a single ``- <marker> <content>`` line.

    Returns one row per related item. Full-width semicolons inside Chinese
    parentheses are kept as translation punctuation; semicolons between closed
    items split the line into separate examples.
    """
    m = LINE_RE.match(line)
    if not m:
        return []

    marker = m.group(1)
    content = m.group(2).strip()

    examples: list[RelatedExample] = []
    for part in _split_outside_parentheses(content):
        jp, zh = _split_item(part)
        if not jp:
            continue
        text, reading = _split_reading(jp)
        if text:
            examples.append(
                RelatedExample(
                    text=text,
                    reading=reading,
                    translation_zh=zh.strip(),
                    category=marker,
                )
            )
    return examples


def _split_item(text: str) -> tuple[str, str]:
    """Split ``japanese（chinese）`` into a (japanese, chinese) pair."""
    # Find the first full-width open paren — the Japanese text never contains （
    idx = text.find("（")
    if idx == -1:
        return (text, "")

    jp = text[:idx].strip()
    zh = text[idx + 1 :].strip()
    # Remove trailing full-width close paren if present
    if zh.endswith("）"):
        zh = zh[:-1].strip()
    return (jp, zh)


def _split_outside_parentheses(content: str) -> list[str]:
    """Split related-form items on separators that are not inside （...）."""
    parts: list[str] = []
    start = 0
    depth = 0
    for index, char in enumerate(content):
        if char in "（(":
            depth += 1
        elif char in "）)" and depth:
            depth -= 1
        elif char in "；;" and depth == 0:
            part = content[start:index].strip()
            if part:
                parts.append(part)
            start = index + 1
    tail = content[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def strip_related_forms_section(markdown: str) -> str:
    """Remove only the ``### Related forms`` section from explanation markdown."""
    lines = str(markdown or "").replace("\r\n", "\n").split("\n")
    output: list[str] = []
    skipping = False

    for line in lines:
        if re.fullmatch(r"\s*###\s+Related forms\s*", line):
            skipping = True
            continue
        if skipping and re.match(r"\s*#{1,3}\s+\S+", line):
            skipping = False
        if skipping:
            continue
        output.append(line.rstrip())

    while output and not output[-1].strip():
        output.pop()
    return "\n".join(output)


def ensure_example_columns(conn: sqlite3.Connection) -> None:
    """Add optional metadata columns needed for related-form example rows."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(entry_examples)")}
    if "category" not in columns:
        conn.execute("ALTER TABLE entry_examples ADD COLUMN category TEXT")
    if "reading" not in columns:
        conn.execute("ALTER TABLE entry_examples ADD COLUMN reading TEXT")
    if "kind" not in columns:
        conn.execute("ALTER TABLE entry_examples ADD COLUMN kind TEXT NOT NULL DEFAULT 'example_sentence'")
        conn.execute("UPDATE entry_examples SET kind='main_sentence' WHERE position=0")
        conn.execute(
            """
            UPDATE entry_examples
               SET kind='related_term'
             WHERE position>0 AND TRIM(COALESCE(category, '')) <> ''
            """
        )


def _source_related_by_index(json_path: Path) -> dict[int, list[str]]:
    if not json_path.exists():
        return {}
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    return {
        int(row["source_index"]): list(row.get("related") or [])
        for row in payload.get("entries", [])
    }


def related_examples_for_entry(row: sqlite3.Row, source_related: dict[int, list[str]]) -> list[RelatedExample]:
    """Read related forms from DB markdown first, then the source JSON fallback."""
    explanation_md = row["explanation_md"] or ""
    lines: list[str] = []
    if "### Related forms" in explanation_md:
        related_section = explanation_md.split("### Related forms", 1)[1]
        lines = [line.strip() for line in related_section.split("\n") if line.strip().startswith("- ")]
    else:
        lines = [f"- {item}" for item in source_related.get(int(row["source_index"]), [])]

    examples: list[RelatedExample] = []
    for line in lines:
        examples.extend(parse_related_line(line))
    return examples


def extract_and_insert(db_path: Path, json_path: Path = DEFAULT_JSON, apply: bool = False) -> dict[str, int]:
    """Parse explanation_md for N2_1500 entries and insert into entry_examples.

    Returns summary counts. In dry-run mode, the database is left unchanged.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    source_related = _source_related_by_index(json_path)

    rows = conn.execute(
        """
        SELECT entry_id, source_index, explanation_md
        FROM entries
        WHERE book_code = 'N2_1500'
        ORDER BY source_index
        """
    ).fetchall()

    inserted = 0
    deleted = 0
    explanations_stripped = 0
    skipped_lines = 0
    touched_entries = 0

    try:
        conn.execute("BEGIN")
        ensure_example_columns(conn)
        delete_categories = RELATED_MARKERS + OLD_CATEGORY_VALUES
        placeholders = ",".join("?" for _ in delete_categories)

        for row in rows:
            examples = related_examples_for_entry(row, source_related)
            if not examples:
                continue
            touched_entries += 1
            entry_id = int(row["entry_id"])
            result = conn.execute(
                f"""
                DELETE FROM entry_examples
                WHERE entry_id = ?
                  AND COALESCE(category, '') IN ({placeholders})
                """,
                (entry_id, *delete_categories),
            )
            deleted += result.rowcount

            start_position = conn.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 FROM entry_examples WHERE entry_id = ?",
                (entry_id,),
            ).fetchone()[0]

            for offset, example in enumerate(examples):
                conn.execute(
                    """
                    INSERT INTO entry_examples(
                      entry_id, position, text, reading, translation_en,
                      translation_zh, explanation_md, audio_clip, category, kind
                    )
                    VALUES (?, ?, ?, ?, '', ?, '', NULL, ?, 'related_term')
                    """,
                    (
                        entry_id,
                        start_position + offset,
                        example.text,
                        example.reading,
                        example.translation_zh,
                        example.category,
                    ),
                )
                inserted += 1

            stripped = strip_related_forms_section(row["explanation_md"] or "")
            if stripped != (row["explanation_md"] or ""):
                conn.execute(
                    "UPDATE entries SET explanation_md = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE entry_id = ?",
                    (stripped, entry_id),
                )
                explanations_stripped += 1

        if apply:
            conn.commit()
        else:
            conn.rollback()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "entries_scanned": len(rows),
        "entries_with_related_forms": touched_entries,
        "deleted_existing_related_examples": deleted,
        "inserted_examples": inserted,
        "explanations_stripped": explanations_stripped,
        "skipped_lines": skipped_lines,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract N2_1500 related forms into entry_examples"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help="Path to SQLite database (default: wordService/data/n2vocab.sqlite)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=DEFAULT_JSON,
        help="Source JSON fallback for idempotent reruns after explanation cleanup.",
    )
    parser.add_argument("--apply", action="store_true", help="Write changes to SQLite.")
    parser.add_argument("--no-backup", action="store_true", help="Skip the apply-mode DB backup.")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"error: database not found at {args.db}")
        raise SystemExit(1)

    print(f"db: {args.db}")
    if args.apply and not args.no_backup:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = args.db.with_name(f"{args.db.name}.backup_before_related_forms_extract_{stamp}")
        shutil.copy2(args.db, backup_path)
        print(f"backup: {backup_path}")
    summary = extract_and_insert(args.db, args.json, apply=args.apply)
    mode = "applied" if args.apply else "dry-run"
    print(json.dumps({"mode": mode, **summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
