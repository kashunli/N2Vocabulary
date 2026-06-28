"""Extract and import the vocabulary from ``N2必背1500词（PDF版）.pdf``.

PyMuPDF is used deliberately: the PDF has selectable text, but Poppler and
pypdf decode its embedded Japanese fonts incorrectly.  The extracted JSON is
kept as a human-auditable intermediate artifact, so later imports do not need
to reopen or reinterpret the PDF.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from extract_related_forms import (
    ensure_example_columns,
    parse_related_line,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PDF = PROJECT_ROOT / "N2必背1500词（PDF版）.pdf"
DEFAULT_JSON = PROJECT_ROOT / "data" / "n2_must_1500_vocab.json"
DEFAULT_DB = PROJECT_ROOT / "wordService" / "data" / "n2vocab.sqlite"
DEFAULT_SUMMARY = PROJECT_ROOT / "output" / "n2_must_1500_import_summary.json"

BOOK_CODE = "N2_1500"
BOOK_TITLE = "N2 必背1500词"
ORIGINAL_PDF_ENTRY_COUNT = 1488
SECTION_STARTS = {
    1: "名词",
    103: "动词",
    138: "イ形容词",
    143: "ナ形容词",
    154: "连体词",
    155: "副词",
    166: "接续词",
    168: "接头词·接尾词",
    170: "外来语",
}
SECTION_ORDER = {title: number for number, title in enumerate(SECTION_STARTS.values(), 1)}
STANDALONE_NOISE = set(SECTION_STARTS.values()) | {"連", "対", "慣", "合", "類"}
RELATION_MARKERS = {"連", "対", "慣", "合", "類"}
ACCENT_CHARS = "⓪①②③④⑤⑥⑦⑧⑨"
POS_RE = re.compile(r"^［([^］]+)］\s*(.*)$")
ENGLISH_MEANING_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


def section_for_page(page_number: int) -> str:
    starts = [start for start in SECTION_STARTS if start <= page_number]
    return SECTION_STARTS[max(starts)]


def page_lines(page: Any, page_number: int) -> list[str]:
    """Return reading-order content while dropping PDF decoration duplicates."""
    lines = [line.strip() for line in page.get_text().splitlines() if line.strip()]
    page_label = f"· {page_number} ·"
    return [
        line
        for line in lines
        if line != page_label
        and line not in STANDALONE_NOISE
        and not re.fullmatch(r"[ぁ-んァ-ンー]", line.strip())
    ]


def is_related_line(line: str) -> bool:
    return len(line) > 1 and line[0] in RELATION_MARKERS and line[1].isspace()


def clean_headword(headword_line: str) -> dict[str, str]:
    accent_match = re.search(rf"([{ACCENT_CHARS}]+)\s*$", headword_line)
    accent = accent_match.group(1) if accent_match else ""
    core = headword_line[: accent_match.start()].strip() if accent_match else headword_line.strip()

    # In one entry, InDesign emits the small ``する`` annotation before the
    # bracketed spelling in reading order. Put it back into the source form.
    reordered = re.fullmatch(r"(.+?)【する】【(.+?)（する】）", core)
    if reordered:
        core = f"{reordered.group(1)}【{reordered.group(2)}（する）】"

    bracket = re.fullmatch(r"(.+?)【(.+?)】", core)
    if bracket:
        reading = bracket.group(1).strip()
        bracket_form = bracket.group(2).strip()
        # ``ダブる【double】`` uses brackets for etymology rather than kanji.
        display = bracket_form if re.search(r"[\u3400-\u9fff々]", bracket_form) else reading
    else:
        # Loanwords include an English etymology in parentheses. It is useful
        # source metadata, but is not part of the learner-facing headword.
        etymology = re.search(r"\s+[(（〈].*$", core)
        display = core[: etymology.start()].strip() if etymology else core.strip()
        reading = display

    return {
        "headword": display,
        "reading": reading if reading != display or re.search(r"[ぁ-んァ-ン]", reading) else "",
        "accent": accent,
        "source_headword": core,
    }


def parse_entries(tagged_lines: list[tuple[int, str]]) -> list[dict[str, Any]]:
    pos_indexes = [index for index, (_, line) in enumerate(tagged_lines) if POS_RE.match(line)]
    entries: list[dict[str, Any]] = []

    for source_index, pos_index in enumerate(pos_indexes, 1):
        page_number, pos_line = tagged_lines[pos_index]
        pos_match = POS_RE.match(pos_line)
        assert pos_match is not None

        headword_index = pos_index - 1
        while headword_index >= 0 and is_related_line(tagged_lines[headword_index][1]):
            headword_index -= 1
        if headword_index < 0:
            raise ValueError(f"missing headword before page {page_number}: {pos_line}")

        headword_page, headword_line = tagged_lines[headword_index]
        next_headword_index = len(tagged_lines)
        if source_index < len(pos_indexes):
            next_headword_index = pos_indexes[source_index] - 1

        related = [
            line
            for _, line in tagged_lines[pos_index + 1 : next_headword_index]
            if is_related_line(line)
        ]
        word = clean_headword(headword_line)
        entries.append(
            {
                "source_index": source_index,
                "source_page": headword_page,
                "section": section_for_page(headword_page),
                **word,
                "part_of_speech": pos_match.group(1).strip(),
                "meaning_zh": pos_match.group(2).strip(),
                "related": related,
            }
        )
    return entries


def extract_pdf(pdf_path: Path) -> dict[str, Any]:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PDF extraction requires PyMuPDF: python -m pip install PyMuPDF") from exc

    tagged_lines: list[tuple[int, str]] = []
    with fitz.open(pdf_path) as document:
        if len(document) != 177:
            raise ValueError(f"expected 177 PDF pages, found {len(document)}")
        for page_number, page in enumerate(document, 1):
            tagged_lines.extend((page_number, line) for line in page_lines(page, page_number))

    entries = parse_entries(tagged_lines)
    validate_entries(entries)
    return {
        "book_code": BOOK_CODE,
        "title": BOOK_TITLE,
        "source_pdf": pdf_path.name,
        "extraction_method": "PyMuPDF embedded text layer",
        "entry_count": len(entries),
        "sections": [
            {"number": SECTION_ORDER[title], "title": title}
            for title in SECTION_ORDER
        ],
        "entries": entries,
    }


def validate_entries(entries: Iterable[dict[str, Any]]) -> None:
    rows = list(entries)
    if len(rows) < ORIGINAL_PDF_ENTRY_COUNT:
        raise ValueError(f"expected at least {ORIGINAL_PDF_ENTRY_COUNT} entry blocks, found {len(rows)}")
    for expected_index, row in enumerate(rows, 1):
        if row["source_index"] != expected_index:
            raise ValueError(f"non-contiguous source index at {expected_index}")
        for field in ("headword", "part_of_speech", "meaning_zh"):
            if not row[field].strip():
                raise ValueError(f"entry {expected_index} has blank {field}")
        if row["section"] not in SECTION_ORDER:
            raise ValueError(f"entry {expected_index} has unknown section {row['section']!r}")
        meaning_en = str(row.get("meaning_en", "")).strip()
        if "\n" in meaning_en:
            raise ValueError(f"entry {expected_index} has multiline meaning_en")
        if ENGLISH_MEANING_CJK_RE.search(meaning_en):
            raise ValueError(f"entry {expected_index} meaning_en contains Japanese or Chinese text")


def explanation_for(row: dict[str, Any]) -> str:
    lines = [f"**Accent:** {row['accent'] or 'not marked'}", f"**Part of speech:** {row['part_of_speech']}"]
    if row["source_headword"] != row["headword"]:
        lines.append(f"**Source form:** {row['source_headword']}")
    return "\n".join(lines)


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def import_rows(db_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    entries = payload["entries"]
    validate_entries(entries)
    positions: dict[int, int] = defaultdict(int)
    connection = connect(db_path)
    try:
        connection.execute("BEGIN")
        ensure_example_columns(connection)
        connection.execute(
            """
            INSERT INTO books(code, title, notes)
            VALUES(?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET title=excluded.title, notes=excluded.notes
            """,
            (
                BOOK_CODE,
                BOOK_TITLE,
                (
                    "Extracted from N2必背1500词（PDF版）.pdf using its embedded text layer; "
                    "the PDF contains 1,488 original entry blocks. Later source-reviewed "
                    "additions are appended after the PDF source indexes."
                ),
            ),
        )
        for title, number in SECTION_ORDER.items():
            connection.execute(
                """
                INSERT INTO units(book_code, number, header, title)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(book_code, number) DO UPDATE SET header=excluded.header, title=excluded.title
                """,
                (BOOK_CODE, number, f"Section {number:02d} {title}", title),
            )

        existing = {
            int(row["source_index"]): row["uuid"]
            for row in connection.execute("SELECT source_index, uuid FROM entries WHERE book_code=?", (BOOK_CODE,))
        }
        for row in entries:
            unit_number = SECTION_ORDER[row["section"]]
            positions[unit_number] += 1
            source_index = int(row["source_index"])
            row_uuid = existing.get(source_index) or str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"n2prepare:{BOOK_CODE}:{source_index}")
            )
            connection.execute(
                """
                INSERT INTO entries(
                  uuid, book_code, unit_number, source_index, position,
                  kanji, reading, verb_pattern, meaning_en, meaning_zh,
                  sentence, explanation_md, word_clip, sentence_clip
                ) VALUES(?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, '', ?, NULL, NULL)
                ON CONFLICT(book_code, source_index) DO UPDATE SET
                  unit_number=excluded.unit_number, position=excluded.position,
                  kanji=excluded.kanji, reading=excluded.reading,
                  meaning_en=excluded.meaning_en, meaning_zh=excluded.meaning_zh,
                  sentence=excluded.sentence, explanation_md=excluded.explanation_md,
                  word_clip=excluded.word_clip, sentence_clip=excluded.sentence_clip
                """,
                (
                    row_uuid,
                    BOOK_CODE,
                    unit_number,
                    source_index,
                    positions[unit_number],
                    row["headword"],
                    row["reading"],
                    str(row.get("meaning_en", "")).strip(),
                    row["meaning_zh"],
                    explanation_for(row),
                ),
            )
            entry_id = connection.execute(
                "SELECT entry_id FROM entries WHERE book_code=? AND source_index=?",
                (BOOK_CODE, source_index),
            ).fetchone()["entry_id"]
            connection.execute("DELETE FROM entry_examples WHERE entry_id=?", (entry_id,))
            related_examples = []
            for item in row.get("related") or []:
                related_examples.extend(parse_related_line(f"- {item}"))
            for offset, example in enumerate(related_examples, 1):
                connection.execute(
                    """
                    INSERT INTO entry_examples(
                      entry_id, position, text, reading, translation_en,
                      translation_zh, explanation_md, audio_clip, category, kind
                    )
                    VALUES (?, ?, ?, ?, '', ?, '', NULL, ?, 'related_term')
                    """,
                    (
                        entry_id,
                        offset,
                        example.text,
                        example.reading,
                        example.translation_zh,
                        example.category,
                    ),
                )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()

    return {
        "book_code": BOOK_CODE,
        "db": str(db_path),
        "entries_imported": len(entries),
        "units_imported": len(SECTION_ORDER),
        "section_counts": dict(Counter(row["section"] for row in entries)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--extract-only", action="store_true")
    parser.add_argument("--import-only", action="store_true")
    parser.add_argument("--backup", action="store_true", help="copy the DB before importing")
    args = parser.parse_args()

    if args.extract_only and args.import_only:
        parser.error("--extract-only and --import-only cannot be combined")

    if args.import_only:
        payload = json.loads(args.json.read_text(encoding="utf-8"))
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
        backup_path = args.db.with_name(f"{args.db.name}.backup_before_n2_1500_import_{stamp}")
        shutil.copy2(args.db, backup_path)

    summary = import_rows(args.db, payload)
    summary["json"] = str(args.json)
    previous_backup = None
    if args.summary.exists():
        try:
            previous_backup = json.loads(args.summary.read_text(encoding="utf-8")).get("backup")
        except (json.JSONDecodeError, OSError):
            pass
    summary["backup"] = str(backup_path) if backup_path else previous_backup
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
