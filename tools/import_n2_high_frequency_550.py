"""Extract and import ``N2高频词汇550个`` as a canonical wordService book.

The PDF has a usable selectable text layer.  This importer deliberately keeps a
JSON extraction artifact beside the source PDF so future runs can audit the
parser output before touching SQLite.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import sys
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_DIR = PROJECT_ROOT / "db"
if str(DB_DIR) not in sys.path:
    sys.path.insert(0, str(DB_DIR))

from migrate import apply_all  # type: ignore[import-not-found]  # noqa: E402


DEFAULT_PDF = PROJECT_ROOT / "N2高频词汇550个-分类整理137972411420343518.1ea2d37c82ca89e.pdf"
DEFAULT_JSON = PROJECT_ROOT / "data" / "n2_high_frequency_550_vocab.json"
DEFAULT_DB = PROJECT_ROOT / "wordService" / "data" / "n2vocab.sqlite"
DEFAULT_SUMMARY = PROJECT_ROOT / "output" / "n2_high_frequency_550_import_summary.json"

BOOK_CODE = "N2_HF_550"
BOOK_TITLE = "N2 高频词汇550个"
EXPECTED_PAGE_COUNT = 49
EXPECTED_ENTRY_COUNT = 550
SECTION_ORDER = {"动词": 1, "名词": 2, "形容词": 3, "副词": 4}

ENTRY_START_RE = re.compile(r"^(\d+)\.\s*(.+)$")
HEADWORD_RE = re.compile(r"^(.+?)（([^（）]+)）(?:\s*【([^】]+)】)?\s*$")
EXAMPLE_RE = re.compile(r"^(\d+)）([^：]+)：(.+?)(?:（([^（）]+)）)?$")
OCCURRENCE_RE = re.compile(r"出现次数")


@dataclass(frozen=True)
class Example:
    text: str
    translation_zh: str
    sense: str


def normalize_key(value: str | None) -> str:
    return re.sub(r"\s+", "", value or "")


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def extract_pdf(pdf_path: Path) -> dict[str, Any]:
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("PDF extraction requires pdfplumber") from exc

    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) != EXPECTED_PAGE_COUNT:
            raise ValueError(f"expected {EXPECTED_PAGE_COUNT} PDF pages, found {len(pdf.pages)}")
        pages = [
            page.extract_text(x_tolerance=1, y_tolerance=3) or ""
            for page in pdf.pages
        ]

    entries = parse_text("\n".join(pages))
    validate_entries(entries)
    return {
        "book_code": BOOK_CODE,
        "title": BOOK_TITLE,
        "source_pdf": pdf_path.name,
        "extraction_method": "pdfplumber selectable text layer",
        "page_count": EXPECTED_PAGE_COUNT,
        "entry_count": len(entries),
        "sections": [
            {"number": number, "title": title}
            for title, number in SECTION_ORDER.items()
        ],
        "entries": entries,
    }


def normalize_pdf_text(text: str) -> str:
    # In this PDF the red occurrence badge sometimes appears inline and
    # sometimes as a three-line block. It is source noise, not learner content.
    text = re.sub(r"\s*【出现次数\s*\n\s*\d+\s*\n\s*】", "", text)
    text = re.sub(r"\s*【出现次数\s*\d+\s*】", "", text)
    text = re.sub(r"(?m)^\s*(\d+)\.\s*\n\s*", r"\1. ", text)
    return text


def parse_text(raw_text: str) -> list[dict[str, Any]]:
    lines = [
        line.strip()
        for line in normalize_pdf_text(raw_text).splitlines()
        if line.strip()
    ]
    entries: list[dict[str, Any]] = []
    current_section = ""
    current: dict[str, Any] | None = None

    for line in lines:
        if re.fullmatch(r"\d+", line):
            continue
        section = section_from_line(line)
        if section:
            current_section = section
            continue
        match = ENTRY_START_RE.match(line)
        if match:
            if current is not None:
                entries.append(parse_entry_block(current))
            current = {
                "source_index": int(match.group(1)),
                "section": current_section,
                "header": match.group(2).strip(),
                "body": [],
            }
            continue
        if current is not None:
            current["body"].append(line)

    if current is not None:
        entries.append(parse_entry_block(current))
    return entries


def section_from_line(line: str) -> str:
    for title in SECTION_ORDER:
        if line.startswith(f"{title}（") or line == title:
            return title
    return ""


def parse_entry_block(block: dict[str, Any]) -> dict[str, Any]:
    header_match = HEADWORD_RE.match(block["header"])
    if not header_match:
        raise ValueError(f"cannot parse entry header {block['source_index']}: {block['header']!r}")
    headword = header_match.group(1).strip()
    reading = header_match.group(2).strip()
    verb_pattern = (header_match.group(3) or "").strip()

    examples: list[Example] = []
    notes: list[str] = []
    body = merge_wrapped_body_lines(block["body"])
    for line in body:
        example_match = EXAMPLE_RE.match(line)
        if example_match:
            examples.append(
                Example(
                    text=example_match.group(3).strip(),
                    translation_zh=(example_match.group(4) or "").strip(),
                    sense=example_match.group(2).strip(),
                )
            )
            continue
        if line.startswith("注意："):
            notes.append(line)
            continue
        notes.append(line)

    meaning_zh = "；".join(dict.fromkeys(example.sense for example in examples if example.sense))
    return {
        "source_index": int(block["source_index"]),
        "section": block["section"],
        "headword": headword,
        "reading": reading if reading != headword else "",
        "verb_pattern": verb_pattern,
        "meaning_zh": meaning_zh,
        "examples": [
            {
                "text": example.text,
                "translation_zh": example.translation_zh,
                "sense": example.sense,
            }
            for example in examples
        ],
        "notes": notes,
    }


def merge_wrapped_body_lines(lines: list[str]) -> list[str]:
    merged: list[str] = []
    for line in lines:
        if re.match(r"^\d+）", line) or line.startswith("注意："):
            merged.append(line)
        elif merged:
            merged[-1] = f"{merged[-1]}{line}"
        else:
            merged.append(line)
    return merged


def validate_entries(entries: list[dict[str, Any]]) -> None:
    if len(entries) != EXPECTED_ENTRY_COUNT:
        raise ValueError(f"expected {EXPECTED_ENTRY_COUNT} entries, found {len(entries)}")
    for expected, row in enumerate(entries, start=1):
        if row["source_index"] != expected:
            raise ValueError(f"expected source_index {expected}, found {row['source_index']}")
        if row["section"] not in SECTION_ORDER:
            raise ValueError(f"entry {expected} has unknown section {row['section']!r}")
        if not row["headword"] or not row["reading"] and row["headword"] != "なんとなく":
            # Same-spelling kana rows intentionally leave reading blank.
            pass
        if not row["headword"]:
            raise ValueError(f"entry {expected} has blank headword")
        if OCCURRENCE_RE.search(json.dumps(row, ensure_ascii=False)):
            raise ValueError(f"entry {expected} still contains occurrence-count text")
        if not row["meaning_zh"]:
            raise ValueError(f"entry {expected} has blank meaning_zh")
        if not row["examples"]:
            raise ValueError(f"entry {expected} has no examples")


def explanation_for(row: dict[str, Any]) -> str:
    lines = []
    if row.get("verb_pattern"):
        lines.append(f"**Pattern:** {row['verb_pattern']}")
    lines.extend(row.get("notes") or [])
    return "\n".join(lines).strip()


def import_rows(db_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    entries = list(payload["entries"])
    validate_entries(entries)
    apply_all(db_path)
    conn = connect(db_path)
    try:
        conn.execute("BEGIN")
        ensure_legacy_example_columns(conn)
        upsert_book_and_units(conn)

        positions: defaultdict[int, int] = defaultdict(int)
        counters: Counter[str] = Counter()
        near_matches: list[dict[str, Any]] = []
        for row in entries:
            unit_number = SECTION_ORDER[row["section"]]
            positions[unit_number] += 1
            result = import_one_row(conn, row, unit_number, positions[unit_number])
            counters.update(result["counters"])
            near_matches.extend(result["near_matches"])

        refresh_reports(conn)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    health = check_health(db_path)
    return {
        "book_code": BOOK_CODE,
        "book_title": BOOK_TITLE,
        "db": str(db_path),
        "json": str(DEFAULT_JSON),
        "entries_seen": len(entries),
        "book_entries": count_for_book(db_path, "book_entries"),
        "legacy_entries": count_for_book(db_path, "entries"),
        "exact_item_matches": counters["exact_item_matches"],
        "new_items": counters["new_items"],
        "examples_added": counters["examples_added"],
        "examples_reused": counters["examples_reused"],
        "near_match_candidates": len(near_matches),
        "near_match_report": str(DEFAULT_SUMMARY.with_name("n2_high_frequency_550_near_matches.json")),
        "health": health,
    }


def ensure_legacy_example_columns(conn: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(entry_examples)")
    }
    if "kind" not in columns:
        conn.execute("ALTER TABLE entry_examples ADD COLUMN kind TEXT NOT NULL DEFAULT 'example_sentence'")
    if "category" not in columns:
        conn.execute("ALTER TABLE entry_examples ADD COLUMN category TEXT")
    if "reading" not in columns:
        conn.execute("ALTER TABLE entry_examples ADD COLUMN reading TEXT")


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def upsert_book_and_units(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT INTO books(code, title, notes)
        VALUES(?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET title=excluded.title, notes=excluded.notes
        """,
        (
            BOOK_CODE,
            BOOK_TITLE,
            "Extracted from N2高频词汇550个-分类整理137972411420343518.1ea2d37c82ca89e.pdf; "
            "occurrence-count badges were ignored during extraction.",
        ),
    )
    for title, number in SECTION_ORDER.items():
        conn.execute(
            """
            INSERT INTO units(book_code, number, header, title)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(book_code, number) DO UPDATE SET header=excluded.header, title=excluded.title
            """,
            (BOOK_CODE, number, f"Section {number:02d} {title}", title),
        )


def import_one_row(
    conn: sqlite3.Connection,
    row: dict[str, Any],
    unit_number: int,
    position: int,
) -> dict[str, Any]:
    counters: Counter[str] = Counter()
    near_matches = near_matches_for_row(conn, row)
    item = exact_item(conn, row)
    if item is None:
        item_id = create_item(conn, row)
        counters["new_items"] += 1
    else:
        item_id = int(item["item_id"])
        fill_missing_item_fields(conn, item_id, row)
        counters["exact_item_matches"] += 1

    entry_uuid = upsert_legacy_entry(conn, row, unit_number, position)
    entry_id = int(
        conn.execute(
            "SELECT entry_id FROM entries WHERE book_code=? AND source_index=?",
            (BOOK_CODE, row["source_index"]),
        ).fetchone()["entry_id"]
    )
    upsert_book_entry(conn, entry_id, item_id, entry_uuid, row, unit_number, position)
    upsert_source_note(conn, item_id, entry_uuid, row)
    sync_legacy_examples(conn, entry_id, row)

    existing_main = conn.execute(
        "SELECT 1 FROM item_examples WHERE item_id=? AND (kind='main_sentence' OR position=0) LIMIT 1",
        (item_id,),
    ).fetchone()
    for offset, example in enumerate(row["examples"]):
        preferred_kind = "main_sentence" if offset == 0 and existing_main is None else "example_sentence"
        example_position, created = upsert_item_example(conn, item_id, row, example, preferred_kind)
        if created:
            counters["examples_added"] += 1
            if preferred_kind == "main_sentence":
                existing_main = True
        else:
            counters["examples_reused"] += 1
        conn.execute(
            """
            INSERT OR IGNORE INTO item_example_sources(item_id, position, source_book_code, source_index)
            VALUES(?, ?, ?, ?)
            """,
            (item_id, example_position, BOOK_CODE, row["source_index"]),
        )

    return {
        "counters": counters,
        "near_matches": near_matches,
    }


def exact_item(conn: sqlite3.Connection, row: dict[str, Any]) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT item_id FROM vocabulary_items
        WHERE TRIM(kanji)=? AND TRIM(COALESCE(reading, ''))=?
        """,
        (normalize_key(row["headword"]), normalize_key(row["reading"])),
    ).fetchone()


def near_matches_for_row(conn: sqlite3.Connection, row: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = conn.execute(
        """
        SELECT item_id, kanji, COALESCE(reading, '') AS reading
        FROM vocabulary_items
        WHERE TRIM(kanji)=? OR TRIM(COALESCE(reading, ''))=?
        """,
        (normalize_key(row["headword"]), normalize_key(row["reading"])),
    ).fetchall()
    out = []
    for candidate in candidates:
        if (
            normalize_key(candidate["kanji"]) == normalize_key(row["headword"])
            and normalize_key(candidate["reading"]) == normalize_key(row["reading"])
        ):
            continue
        out.append(
            {
                "source_index": row["source_index"],
                "headword": row["headword"],
                "reading": row["reading"],
                "candidate_item_id": candidate["item_id"],
                "candidate_headword": candidate["kanji"],
                "candidate_reading": candidate["reading"],
            }
        )
    return out


def create_item(conn: sqlite3.Connection, row: dict[str, Any]) -> int:
    item_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"n2prepare:item:{BOOK_CODE}:{row['source_index']}"))
    conn.execute(
        """
        INSERT INTO vocabulary_items(
          uuid, kanji, reading, verb_pattern, meaning_en, meaning_zh,
          explanation_md, word_clip
        )
        VALUES(?, ?, ?, ?, '', ?, ?, NULL)
        """,
        (
            item_uuid,
            row["headword"],
            row["reading"] or None,
            row["verb_pattern"] or None,
            row["meaning_zh"],
            explanation_for(row),
        ),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def fill_missing_item_fields(conn: sqlite3.Connection, item_id: int, row: dict[str, Any]) -> None:
    conn.execute(
        """
        UPDATE vocabulary_items
           SET verb_pattern = COALESCE(NULLIF(verb_pattern, ''), ?),
               meaning_zh = COALESCE(NULLIF(meaning_zh, ''), ?),
               explanation_md = COALESCE(NULLIF(explanation_md, ''), ?),
               updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
         WHERE item_id = ?
        """,
        (row["verb_pattern"] or None, row["meaning_zh"], explanation_for(row) or None, item_id),
    )


def upsert_legacy_entry(
    conn: sqlite3.Connection,
    row: dict[str, Any],
    unit_number: int,
    position: int,
) -> str:
    existing = conn.execute(
        "SELECT uuid FROM entries WHERE book_code=? AND source_index=?",
        (BOOK_CODE, row["source_index"]),
    ).fetchone()
    entry_uuid = existing["uuid"] if existing else str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"n2prepare:{BOOK_CODE}:{row['source_index']}")
    )
    first_example = row["examples"][0]
    columns = table_columns(conn, "entries")
    if "headword_text" in columns:
        conn.execute(
            """
            INSERT INTO entries(
              uuid, book_code, unit_number, source_index, position,
              kanji, reading, headword_text, verb_pattern, meaning_en, meaning_zh,
              sentence, explanation_md, word_clip, sentence_clip
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?, NULL, NULL)
            ON CONFLICT(book_code, source_index) DO UPDATE SET
              unit_number=excluded.unit_number,
              position=excluded.position,
              kanji=excluded.kanji,
              reading=excluded.reading,
              headword_text=excluded.headword_text,
              verb_pattern=excluded.verb_pattern,
              meaning_en=excluded.meaning_en,
              meaning_zh=excluded.meaning_zh,
              sentence=excluded.sentence,
              explanation_md=excluded.explanation_md,
              word_clip=excluded.word_clip,
              sentence_clip=excluded.sentence_clip
            """,
            (
                entry_uuid,
                BOOK_CODE,
                unit_number,
                row["source_index"],
                position,
                row["headword"],
                row["reading"] or None,
                row["headword"],
                row["verb_pattern"] or None,
                row["meaning_zh"],
                first_example["text"],
                explanation_for(row),
            ),
        )
    else:
        conn.execute(
            """
            INSERT INTO entries(
              uuid, book_code, unit_number, source_index, position,
              kanji, reading, verb_pattern, meaning_en, meaning_zh,
              sentence, explanation_md, word_clip, sentence_clip
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?, NULL, NULL)
            ON CONFLICT(book_code, source_index) DO UPDATE SET
              unit_number=excluded.unit_number,
              position=excluded.position,
              kanji=excluded.kanji,
              reading=excluded.reading,
              verb_pattern=excluded.verb_pattern,
              meaning_en=excluded.meaning_en,
              meaning_zh=excluded.meaning_zh,
              sentence=excluded.sentence,
              explanation_md=excluded.explanation_md,
              word_clip=excluded.word_clip,
              sentence_clip=excluded.sentence_clip
            """,
            (
                entry_uuid,
                BOOK_CODE,
                unit_number,
                row["source_index"],
                position,
                row["headword"],
                row["reading"] or None,
                row["verb_pattern"] or None,
                row["meaning_zh"],
                first_example["text"],
                explanation_for(row),
            ),
        )
    return entry_uuid


def upsert_book_entry(
    conn: sqlite3.Connection,
    entry_id: int,
    item_id: int,
    entry_uuid: str,
    row: dict[str, Any],
    unit_number: int,
    position: int,
) -> None:
    first_example = row["examples"][0]
    conn.execute(
        """
        INSERT INTO book_entries(
          entry_id, item_id, uuid, book_code, unit_number, source_index,
          position, sentence, explanation_md, sentence_clip
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
        ON CONFLICT(book_code, source_index) DO UPDATE SET
          item_id=excluded.item_id,
          unit_number=excluded.unit_number,
          position=excluded.position,
          sentence=excluded.sentence,
          explanation_md=excluded.explanation_md,
          sentence_clip=excluded.sentence_clip,
          updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
        """,
        (
            entry_id,
            item_id,
            entry_uuid,
            BOOK_CODE,
            unit_number,
            row["source_index"],
            position,
            first_example["text"],
            explanation_for(row),
        ),
    )


def upsert_source_note(
    conn: sqlite3.Connection,
    item_id: int,
    entry_uuid: str,
    row: dict[str, Any],
) -> None:
    first_example = row["examples"][0]
    conn.execute(
        """
        INSERT INTO item_source_notes(
          item_id, source_book_code, source_entry_uuid, source_index,
          source_reading, source_meaning_en, source_meaning_zh,
          source_explanation_md, source_sentence, source_translation_en,
          source_translation_zh, source_word_clip, source_sentence_clip
        )
        VALUES(?, ?, ?, ?, ?, '', ?, ?, ?, '', ?, NULL, NULL)
        ON CONFLICT(item_id, source_book_code, source_index) DO UPDATE SET
          source_entry_uuid=excluded.source_entry_uuid,
          source_reading=excluded.source_reading,
          source_meaning_zh=excluded.source_meaning_zh,
          source_explanation_md=excluded.source_explanation_md,
          source_sentence=excluded.source_sentence,
          source_translation_zh=excluded.source_translation_zh
        """,
        (
            item_id,
            BOOK_CODE,
            entry_uuid,
            row["source_index"],
            row["reading"] or None,
            row["meaning_zh"],
            explanation_for(row),
            first_example["text"],
            first_example["translation_zh"],
        ),
    )


def sync_legacy_examples(conn: sqlite3.Connection, entry_id: int, row: dict[str, Any]) -> None:
    conn.execute("DELETE FROM entry_examples WHERE entry_id=?", (entry_id,))
    for position, example in enumerate(row["examples"]):
        conn.execute(
            """
            INSERT INTO entry_examples(
              entry_id, position, kind, text, reading, translation_en,
              translation_zh, explanation_md, audio_clip, category
            )
            VALUES(?, ?, ?, ?, '', '', ?, ?, NULL, ?)
            """,
            (
                entry_id,
                position,
                "main_sentence" if position == 0 else "example_sentence",
                example["text"],
                example["translation_zh"],
                example.get("sense") or "",
                example.get("sense") or None,
            ),
        )


def upsert_item_example(
    conn: sqlite3.Connection,
    item_id: int,
    row: dict[str, Any],
    example: dict[str, Any],
    preferred_kind: str,
) -> tuple[int, bool]:
    existing = conn.execute(
        """
        SELECT position FROM item_examples
        WHERE item_id=?
          AND TRIM(text)=?
          AND TRIM(COALESCE(reading, ''))=''
          AND TRIM(COALESCE(translation_zh, ''))=?
        ORDER BY position
        LIMIT 1
        """,
        (item_id, example["text"].strip(), example["translation_zh"].strip()),
    ).fetchone()
    if existing:
        return int(existing["position"]), False

    if preferred_kind == "main_sentence":
        position = 0
    else:
        max_position = conn.execute(
            "SELECT MAX(position) FROM item_examples WHERE item_id=?",
            (item_id,),
        ).fetchone()[0]
        position = int(max_position) + 1 if max_position is not None else 0
    conn.execute(
        """
        INSERT INTO item_examples(
          item_id, position, kind, text, reading, translation_en,
          translation_zh, explanation_md, audio_clip, category
        )
        VALUES(?, ?, ?, ?, '', '', ?, ?, NULL, ?)
        """,
        (
            item_id,
            position,
            preferred_kind,
            example["text"],
            example["translation_zh"],
            example.get("sense") or "",
            example.get("sense") or None,
        ),
    )
    return position, True


def refresh_reports(conn: sqlite3.Connection) -> None:
    conn.execute(
        "DELETE FROM vocabulary_migration_reports WHERE kind IN (?, ?)",
        ("n2_hf_550_same_headword", "n2_hf_550_same_reading"),
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO vocabulary_migration_reports(kind, group_key, detail, row_count)
        SELECT
          'n2_hf_550_same_headword',
          v.kanji,
          GROUP_CONCAT(DISTINCT COALESCE(v.reading, '') || '@' || be.book_code || ':' || be.source_index),
          COUNT(DISTINCT COALESCE(v.reading, ''))
        FROM book_entries be
        JOIN vocabulary_items v ON v.item_id = be.item_id
        WHERE v.kanji IN (
          SELECT v2.kanji
          FROM book_entries be2
          JOIN vocabulary_items v2 ON v2.item_id = be2.item_id
          WHERE be2.book_code = ?
        )
        GROUP BY v.kanji
        HAVING COUNT(DISTINCT COALESCE(v.reading, '')) > 1
        """,
        (BOOK_CODE,),
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO vocabulary_migration_reports(kind, group_key, detail, row_count)
        SELECT
          'n2_hf_550_same_reading',
          COALESCE(v.reading, ''),
          GROUP_CONCAT(DISTINCT v.kanji || '@' || be.book_code || ':' || be.source_index),
          COUNT(DISTINCT v.kanji)
        FROM book_entries be
        JOIN vocabulary_items v ON v.item_id = be.item_id
        WHERE COALESCE(v.reading, '') <> ''
          AND COALESCE(v.reading, '') IN (
            SELECT COALESCE(v2.reading, '')
            FROM book_entries be2
            JOIN vocabulary_items v2 ON v2.item_id = be2.item_id
            WHERE be2.book_code = ?
          )
        GROUP BY COALESCE(v.reading, '')
        HAVING COUNT(DISTINCT v.kanji) > 1
        """,
        (BOOK_CODE,),
    )


def count_for_book(db_path: Path, table: str) -> int:
    conn = connect(db_path)
    try:
        return int(
            conn.execute(f"SELECT COUNT(*) FROM {table} WHERE book_code=?", (BOOK_CODE,)).fetchone()[0]
        )
    finally:
        conn.close()


def check_health(db_path: Path) -> dict[str, Any]:
    conn = connect(db_path)
    try:
        return {
            "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
            "foreign_key_check_rows": len(conn.execute("PRAGMA foreign_key_check").fetchall()),
        }
    finally:
        conn.close()


def write_near_match_report(db_path: Path, report_path: Path) -> int:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT kind, group_key, detail, row_count
            FROM vocabulary_migration_reports
            WHERE kind IN ('n2_hf_550_same_headword', 'n2_hf_550_same_reading')
            ORDER BY kind, group_key
            """
        ).fetchall()
    finally:
        conn.close()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps([dict(row) for row in rows], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--extract-only", action="store_true")
    parser.add_argument("--import-only", action="store_true")
    parser.add_argument("--backup", action="store_true")
    args = parser.parse_args()

    if args.extract_only and args.import_only:
        parser.error("--extract-only and --import-only cannot be combined")

    if args.import_only:
        payload = json.loads(args.json.read_text(encoding="utf-8"))
        validate_entries(payload["entries"])
    else:
        payload = extract_pdf(args.pdf)
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.extract_only:
        print(json.dumps({"json": str(args.json), "entries": payload["entry_count"]}, ensure_ascii=False, indent=2))
        return

    backup_path = None
    if args.backup:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = args.db.with_name(f"{args.db.name}.backup_before_n2_hf_550_import_{stamp}")
        shutil.copy2(args.db, backup_path)

    summary = import_rows(args.db, payload)
    if backup_path:
        summary["backup"] = str(backup_path)
    report_path = args.summary.with_name("n2_high_frequency_550_near_matches.json")
    summary["near_match_report_rows"] = write_near_match_report(args.db, report_path)
    summary["near_match_report"] = str(report_path)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
