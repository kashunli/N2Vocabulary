"""
Import GreenWordBook N2 vocabulary into the shared wordService SQLite database.

The GreenWordBook source is already a structured OCR output. This importer keeps
that source read-only, maps it into book_code=GWB_N2, and writes a small summary
that future agents can use to audit what changed.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from merge_gwb_duplicates import apply_merge


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "wordService" / "data" / "n2vocab.sqlite"
DEFAULT_GREEN_ROOT = Path(r"D:\n2Prepare\greenWordBook")
DEFAULT_SUMMARY = PROJECT_ROOT / "output" / "green_word_book_import_summary.json"
BOOK_CODE = "GWB_N2"
BOOK_TITLE = "无敌绿宝书 N2 词汇"
LANGUAGE_ORIGIN_RE = re.compile(r"^(?:英|米|法|德|徳|独|意|葡|蘭|荷|露|梵|希)\s*[A-Za-z]")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def ensure_import_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS word_service_settings (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL,
          updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        )
        """
    )


def green_word_records(green_root: Path) -> list[dict[str, Any]]:
    payload = read_json(green_root / "data" / "green_word_book_n2_vocab.json")
    records = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError("GreenWordBook vocabulary JSON must contain a records list")
    return records


def manifest_pages(green_root: Path) -> list[dict[str, Any]]:
    payload = read_json(green_root / "material" / "page_manifest.json")
    pages = payload.get("pages") if isinstance(payload, dict) else payload
    if isinstance(pages, dict):
        pages = list(pages.values())
    if not isinstance(pages, list):
        raise ValueError("GreenWordBook page manifest must contain pages")
    return [page for page in pages if isinstance(page, dict)]


def parse_unit_number(*values: Any) -> int | None:
    for value in values:
        text = str(value or "")
        match = re.search(r"第\s*(\d+)\s*单元", text)
        if match:
            return int(match.group(1))
    return None


def derive_page_units(pages: list[dict[str, Any]]) -> dict[int, int]:
    """Map source PDF page to unit, carrying the latest manifest heading forward."""
    page_units: dict[int, int] = {}
    current_unit: int | None = None
    sorted_pages = sorted(
        pages,
        key=lambda page: int(page.get("source_pdf_page") or page.get("printed_page") or 0),
    )
    for page in sorted_pages:
        page_number = page.get("source_pdf_page")
        if page_number is None:
            continue
        parsed_unit = parse_unit_number(page.get("title"), page.get("section"))
        if parsed_unit is not None:
            current_unit = parsed_unit
        if current_unit is not None:
            page_units[int(page_number)] = current_unit
    return page_units


def assign_units(
    records: list[dict[str, Any]], page_units: dict[int, int]
) -> tuple[list[int], Counter[str]]:
    units: list[int] = []
    current_section_unit: int | None = None
    sources: Counter[str] = Counter()

    for record in records:
        page_number = record.get("source_pdf_page")
        if page_number is not None and int(page_number) in page_units:
            units.append(page_units[int(page_number)])
            sources["page_manifest"] += 1
            parsed_section_unit = parse_unit_number(record.get("section"))
            if parsed_section_unit is not None:
                current_section_unit = parsed_section_unit
            continue

        parsed_section_unit = parse_unit_number(record.get("section"))
        if parsed_section_unit is not None:
            current_section_unit = parsed_section_unit
            units.append(parsed_section_unit)
            sources["record_section"] += 1
            continue

        # Unit 0 should be rare. It keeps otherwise valid rows visible without
        # inventing a page relationship the source does not prove.
        units.append(current_section_unit or 0)
        sources["fallback"] += 1

    return units, sources


def unit_title(unit_number: int) -> str:
    if unit_number == 0:
        return "Unassigned source rows"
    return f"第{unit_number}单元"


def clean_bracket_form(value: str) -> str:
    text = (value or "").strip()
    if (text.startswith("【") and text.endswith("】")) or (
        text.startswith("[") and text.endswith("]")
    ):
        return text[1:-1].strip()
    return text


def is_bracketed(value: str) -> bool:
    text = (value or "").strip()
    return (text.startswith("【") and text.endswith("】")) or (
        text.startswith("[") and text.endswith("]")
    )


def has_misplaced_bracket_form(record: dict[str, Any]) -> bool:
    return not str(record.get("bracket_form") or "").strip() and is_bracketed(
        str(record.get("reading") or "")
    )


def is_language_origin_note(value: str) -> bool:
    """Return true for GWB bracket notes like ``法 jupon`` or ``荷 koffie``.

    These notes explain the source language of a loanword; they are useful
    learner context, but should not replace the Japanese katakana headword.
    """
    return bool(LANGUAGE_ORIGIN_RE.match((value or "").strip()))


def display_word(record: dict[str, Any]) -> tuple[str, str]:
    headword = str(record.get("headword") or "").strip()
    bracket = clean_bracket_form(str(record.get("bracket_form") or ""))
    reading = str(record.get("reading") or "").strip()
    if has_misplaced_bracket_form(record):
        # Some OCR batches put 【削る】 in reading instead of bracket_form.
        bracket = clean_bracket_form(reading)
        reading = ""
    if bracket:
        # GWB consistently uses headword【display form】: for example,
        # あいかわらず【相変わらず】 and アイスクリーム【ice cream】.
        # Map both patterns to the service's normal display/reading pair.
        if is_language_origin_note(bracket):
            return headword, bracket
        return bracket, reading or headword
    return headword, reading


def markdown_list(label: str, items: list[Any]) -> list[str]:
    clean_items = [str(item).strip() for item in items if str(item).strip()]
    if not clean_items:
        return []
    return [f"- **{label}:** {', '.join(clean_items)}"]


def exam_question_markdown(questions: list[dict[str, Any]]) -> list[str]:
    if not questions:
        return []
    lines = ["", "### Exam Questions"]
    for index, question in enumerate(questions, start=1):
        prompt = str(question.get("question_japanese") or "").strip()
        year = str(question.get("year_level") or "").strip()
        label = f"{index}. {prompt}" if prompt else f"{index}."
        if year:
            label = f"{label} ({year})"
        lines.append(label)
        choices = [str(choice).strip() for choice in question.get("choices") or [] if str(choice).strip()]
        lines.extend(f"- {choice}" for choice in choices)
        analysis = str(question.get("analysis_chinese") or "").strip()
        if analysis:
            lines.append(f"- Analysis: {analysis}")
    return lines


def explanation_markdown(record: dict[str, Any], _source_index: int) -> str:
    lines: list[str] = []
    if record.get("needs_review"):
        lines.extend(
            [
                "**Needs review:** This row was marked by the GreenWordBook OCR/parser workflow.",
                "",
                "---",
                "",
            ]
        )

    # Source provenance remains available in the import JSON and database keys.
    # The learner-facing detail panel should contain study notes, not OCR bookkeeping.
    lines.extend(markdown_list("Near synonyms", record.get("near_synonyms") or []))
    lines.extend(markdown_list("Opposites", record.get("opposites") or []))
    lines.extend(markdown_list("Idioms / collocations", record.get("idioms_or_collocations") or []))

    notes = str(record.get("notes") or "").strip()
    if notes:
        lines.append(f"- **Notes:** {notes}")

    lines.extend(exam_question_markdown(record.get("exam_questions") or []))
    return "\n".join(lines).strip()


def import_green_word_book(db_path: Path, green_root: Path) -> dict[str, Any]:
    records = green_word_records(green_root)
    units, unit_sources = assign_units(records, derive_page_units(manifest_pages(green_root)))
    unit_numbers = sorted(set(units))
    position_by_unit: defaultdict[int, int] = defaultdict(int)
    unit_counts: Counter[int] = Counter(units)
    examples_imported = 0
    review_ids: list[str] = []
    empty_counts: Counter[str] = Counter()

    conn = connect(db_path)
    try:
        ensure_import_schema(conn)
        conn.execute("BEGIN")
        conn.execute(
            """
            INSERT INTO books(code, title, notes)
            VALUES(?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
              title = excluded.title,
              notes = excluded.notes
            """,
            (
                BOOK_CODE,
                BOOK_TITLE,
                f"Imported from {green_root / 'data' / 'green_word_book_n2_vocab.json'}",
            ),
        )

        for unit_number in unit_numbers:
            title = unit_title(unit_number)
            header = title if unit_number == 0 else f"Unit {unit_number:02d} {title}"
            conn.execute(
                """
                INSERT INTO units(book_code, number, header, title)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(book_code, number) DO UPDATE SET
                  header = excluded.header,
                  title = excluded.title
                """,
                (BOOK_CODE, unit_number, header, title),
            )

        existing_uuid = {
            int(row["source_index"]): row["uuid"]
            for row in conn.execute(
                "SELECT source_index, uuid FROM entries WHERE book_code = ?",
                (BOOK_CODE,),
            )
        }

        for source_index, (record, unit_number) in enumerate(zip(records, units), start=1):
            position_by_unit[unit_number] += 1
            kanji, reading = display_word(record)
            sentence = str(record.get("example_japanese") or "").strip()
            sentence_translation_zh = str(record.get("example_chinese") or "").strip()
            meaning_zh = str(record.get("chinese_meaning") or "").strip()
            if not kanji:
                empty_counts["headword"] += 1
            if not meaning_zh:
                empty_counts["meaning_zh"] += 1
            if not sentence:
                empty_counts["example_japanese"] += 1
            if record.get("needs_review"):
                review_ids.append(str(record.get("id") or source_index))

            row_uuid = existing_uuid.get(source_index) or str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"n2prepare:{BOOK_CODE}:{source_index}")
            )
            conn.execute(
                """
                INSERT INTO entries(
                  uuid, book_code, unit_number, source_index, position,
                  kanji, reading, verb_pattern, meaning_en, meaning_zh,
                  sentence, explanation_md, word_clip, sentence_clip
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, NULL, '', ?, ?, ?, NULL, NULL)
                ON CONFLICT(book_code, source_index) DO UPDATE SET
                  unit_number = excluded.unit_number,
                  position = excluded.position,
                  kanji = excluded.kanji,
                  reading = excluded.reading,
                  verb_pattern = excluded.verb_pattern,
                  meaning_en = excluded.meaning_en,
                  meaning_zh = excluded.meaning_zh,
                  sentence = excluded.sentence,
                  explanation_md = excluded.explanation_md,
                  word_clip = excluded.word_clip,
                  sentence_clip = excluded.sentence_clip
                """,
                (
                    row_uuid,
                    BOOK_CODE,
                    unit_number,
                    source_index,
                    position_by_unit[unit_number],
                    kanji,
                    reading,
                    meaning_zh,
                    sentence,
                    explanation_markdown(record, source_index),
                ),
            )
            entry_id = conn.execute(
                "SELECT entry_id FROM entries WHERE book_code = ? AND source_index = ?",
                (BOOK_CODE, source_index),
            ).fetchone()["entry_id"]
            conn.execute("DELETE FROM entry_examples WHERE entry_id = ?", (entry_id,))
            if sentence or sentence_translation_zh:
                conn.execute(
                    """
                    INSERT INTO entry_examples(
                      entry_id, position, kind, text, translation_en, translation_zh, explanation_md, audio_clip
                    )
                    VALUES(?, 0, 'main_sentence', ?, '', ?, '', NULL)
                    """,
                    (entry_id, sentence, sentence_translation_zh),
                )
                examples_imported += 1

        conn.execute(
            """
            INSERT INTO word_service_settings(key, value, updated_at)
            VALUES('green_word_book_import_source', ?, ?)
            ON CONFLICT(key) DO UPDATE SET
              value = excluded.value,
              updated_at = excluded.updated_at
            """,
            (str(green_root), now_utc()),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    summary = {
        "db": str(db_path),
        "source": str(green_root),
        "book_code": BOOK_CODE,
        "book_title": BOOK_TITLE,
        "words_seen": len(records),
        "words_imported": len(records),
        "examples_imported": examples_imported,
        "units_imported": len(unit_numbers),
        "unit_counts": {str(unit): unit_counts[unit] for unit in unit_numbers},
        "unit_derivation_sources": dict(unit_sources),
        "needs_review_count": len(review_ids),
        "needs_review_ids": review_ids,
        "empty_field_counts": dict(empty_counts),
        "bracketed_readings_normalized": sum(
            has_misplaced_bracket_form(record) for record in records
        ),
    }
    # Keep the browsable GWB book free of exact N2/N3 duplicates. The merge is
    # independently idempotent and preserves its own backup/audit summary.
    summary["duplicate_merge"] = apply_merge(db_path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB), help="wordService SQLite database")
    parser.add_argument("--green-root", default=str(DEFAULT_GREEN_ROOT), help="GreenWordBook project root")
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY), help="summary JSON output")
    args = parser.parse_args()

    summary = import_green_word_book(Path(args.db), Path(args.green_root))
    summary_path = Path(args.summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
