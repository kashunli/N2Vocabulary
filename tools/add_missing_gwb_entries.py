#!/usr/bin/env python3
"""Add GreenWordBook N2 records missing from the WordService DB.

The GWB_N2 book in the DB was imported from an earlier OCR snapshot and then
pruned by the legacy duplicate merge, so it lacks records that exist in the
current `green_word_book_n2_vocab.json` (e.g. うけとる, えいきょう). This tool
adds exactly those missing records to the runtime tables without touching any
existing rows:

  - legacy `entries` + `entry_examples` (source of record),
  - `book_entries` (runtime per-book placements),
  - `vocabulary_items` (reuse the shared item when (kanji, reading) already
    exists, otherwise create a fresh item),
  - `item_examples` + `item_example_sources` + `item_source_notes`
    (runtime example/provenance tables).

Identity is the record's 1-based position in the JSON (== book_entries
source_index). Example audio is left NULL; the separate cut-audio importer
attaches it afterwards.

Run with --dry-run first.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sqlite3
import sys
import uuid
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from import_green_word_book import (
    BOOK_CODE,
    assign_units,
    derive_page_units,
    display_word,
    explanation_markdown,
    manifest_pages,
    now_utc,
    unit_title,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "wordService" / "data" / "n2vocab.sqlite"
DEFAULT_GREEN_ROOT = Path(r"D:\n2Prepare\greenWordBook")
DEFAULT_SUMMARY = PROJECT_ROOT / "output" / "gwb_missing_entries_import_summary.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"\s+", "", t)


def row_uuid(source_index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"n2prepare:{BOOK_CODE}:{source_index}"))


def compute_missing(records: list[dict], conn: sqlite3.Connection) -> list[dict]:
    cur = conn.cursor()
    existing_indexes = {
        r[0]
        for r in cur.execute(
            "SELECT source_index FROM book_entries WHERE book_code=?", (BOOK_CODE,)
        )
    }
    existing_example_texts = {
        r[0]
        for r in cur.execute(
            "SELECT DISTINCT text FROM entry_examples ex "
            "JOIN book_entries be ON be.entry_id = ex.entry_id "
            "WHERE be.book_code=?",
            (BOOK_CODE,),
        )
    }

    missing = []
    for pos, rec in enumerate(records, start=1):
        if pos in existing_indexes:
            continue
        kanji, reading = display_word(rec)
        sentence = str(rec.get("example_japanese") or "").strip()
        missing.append(
            {
                "source_index": pos,
                "record": rec,
                "kanji": kanji,
                "reading": reading,
                "sentence": sentence,
                "text_already_in_db": bool(sentence) and norm(sentence) in existing_example_texts,
            }
        )
    return missing


def ensure_units(conn: sqlite3.Connection, unit_numbers: set[int]) -> None:
    for unit in sorted(unit_numbers):
        title = unit_title(unit)
        header = title if unit == 0 else f"Unit {unit:02d} {title}"
        conn.execute(
            """
            INSERT INTO units(book_code, number, header, title)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(book_code, number) DO UPDATE SET
              header = excluded.header, title = excluded.title
            """,
            (BOOK_CODE, unit, header, title),
        )


def add_missing(db_path: Path, green_root: Path) -> dict[str, Any]:
    payload = read_json(green_root / "data" / "green_word_book_n2_vocab.json")
    records = payload["records"]
    units, _ = assign_units(records, derive_page_units(manifest_pages(green_root)))

    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        missing = compute_missing(records, conn)
        if not missing:
            return {"added": 0}

        # Unit positions exactly as the full importer would assign them.
        position_by_unit: defaultdict[int, int] = defaultdict(int)
        missing_by_index = {m["source_index"]: m for m in missing}
        for pos, (rec, unit) in enumerate(zip(records, units), start=1):
            position_by_unit[unit] += 1
            if pos in missing_by_index:
                missing_by_index[pos]["unit_number"] = unit
                missing_by_index[pos]["position"] = position_by_unit[unit]

        # Existing items by normalized (kanji, reading).
        item_lookup = {}
        for item_id, kanji, reading in conn.execute(
            "SELECT item_id, kanji, reading FROM vocabulary_items"
        ).fetchall():
            key = ((kanji or "").strip(), (reading or "").strip())
            if key not in item_lookup:
                item_lookup[key] = item_id

        conn.execute("BEGIN IMMEDIATE")
        try:
            ensure_units(conn, {m["unit_number"] for m in missing})
            # 1) legacy entries + entry_examples.
            for m in missing:
                rec = m["record"]
                cur = conn.execute(
                    """
                    INSERT INTO entries(
                      uuid, book_code, unit_number, source_index, position,
                      kanji, reading, verb_pattern, meaning_en, meaning_zh,
                      sentence, explanation_md, word_clip, sentence_clip
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, NULL, '', ?, ?, ?, NULL, NULL)
                    """,
                    (
                        row_uuid(m["source_index"]),
                        BOOK_CODE,
                        m["unit_number"],
                        m["source_index"],
                        m["position"],
                        m["kanji"],
                        m["reading"],
                        str(rec.get("chinese_meaning") or "").strip(),
                        m["sentence"],
                        explanation_markdown(rec, m["source_index"]),
                    ),
                )
                m["entry_id"] = cur.lastrowid
                translation_zh = str(rec.get("example_chinese") or "").strip()
                if m["sentence"] or translation_zh:
                    conn.execute(
                        """
                        INSERT INTO entry_examples(
                          entry_id, position, kind, text, translation_en,
                          translation_zh, explanation_md, audio_clip
                        ) VALUES(?, 0, 'main_sentence', ?, '', ?, '', NULL)
                        """,
                        (m["entry_id"], m["sentence"], translation_zh),
                    )

            # 2) vocabulary_items: reuse shared items, else one item per new key.
            new_item_by_key: dict[tuple[str, str], dict[str, Any]] = {}
            for m in missing:
                key = (m["kanji"], m["reading"])
                item_id = item_lookup.get(key)
                if item_id is None:
                    holder = new_item_by_key.setdefault(
                        key, {"entries": [], "kanji": m["kanji"], "reading": m["reading"]}
                    )
                    holder["entries"].append(m)
                m["item_id"] = item_id

            for key, holder in new_item_by_key.items():
                first = holder["entries"][0]
                cur = conn.execute(
                    """
                    INSERT INTO vocabulary_items(
                      uuid, kanji, reading, verb_pattern, meaning_en,
                      meaning_zh, explanation_md, word_clip
                    ) VALUES(?, ?, ?, NULL, '', ?, ?, NULL)
                    """,
                    (
                        row_uuid(first["source_index"]),
                        holder["kanji"],
                        holder["reading"],
                        str(first["record"].get("chinese_meaning") or "").strip(),
                        explanation_markdown(first["record"], first["source_index"]),
                    ),
                )
                item_id = cur.lastrowid
                item_lookup[key] = item_id
                for m in holder["entries"]:
                    m["item_id"] = item_id

            # 3) book_entries (runtime placements).
            for m in missing:
                conn.execute(
                    """
                    INSERT INTO book_entries(
                      entry_id, item_id, uuid, book_code, unit_number,
                      source_index, position, sentence, explanation_md,
                      sentence_clip, word_clip, verb_pattern, meaning_en, meaning_zh
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, '', ?)
                    """,
                    (
                        m["entry_id"],
                        m["item_id"],
                        row_uuid(m["source_index"]),
                        BOOK_CODE,
                        m["unit_number"],
                        m["source_index"],
                        m["position"],
                        m["sentence"],
                        explanation_markdown(m["record"], m["source_index"]),
                        str(m["record"].get("chinese_meaning") or "").strip(),
                    ),
                )

            # 4) item examples + provenance.
            for m in missing:
                if not m["sentence"]:
                    continue
                position = None
                for pos, text in conn.execute(
                    "SELECT position, text FROM item_examples WHERE item_id=?",
                    (m["item_id"],),
                ).fetchall():
                    if (text or "").strip() == m["sentence"]:
                        position = pos
                        break
                if position is None:
                    position = conn.execute(
                        "SELECT COALESCE(MAX(position), -1) + 1 FROM item_examples WHERE item_id=?",
                        (m["item_id"],),
                    ).fetchone()[0]
                    conn.execute(
                        """
                        INSERT INTO item_examples(
                          item_id, position, kind, text, reading,
                          translation_en, translation_zh, explanation_md, audio_clip
                        ) VALUES(?, ?, 'example_sentence', ?, ?, '', ?, '', NULL)
                        """,
                        (
                            m["item_id"],
                            position,
                            m["sentence"],
                            (m["record"].get("reading") or "").strip(),
                            str(m["record"].get("example_chinese") or "").strip(),
                        ),
                    )
                conn.execute(
                    """
                    INSERT OR IGNORE INTO item_source_notes(
                      item_id, source_book_code, source_entry_uuid, source_index,
                      source_reading, source_meaning_en, source_meaning_zh,
                      source_explanation_md, source_sentence, source_translation_en,
                      source_translation_zh, source_word_clip, source_sentence_clip
                    ) VALUES(?, ?, ?, ?, ?, '', ?, ?, ?, NULL, ?, NULL, NULL)
                    """,
                    (
                        m["item_id"],
                        BOOK_CODE,
                        row_uuid(m["source_index"]),
                        m["source_index"],
                        (m["record"].get("reading") or "").strip(),
                        str(m["record"].get("chinese_meaning") or "").strip(),
                        explanation_markdown(m["record"], m["source_index"]),
                        m["sentence"],
                        str(m["record"].get("example_chinese") or "").strip(),
                    ),
                )
                conn.execute(
                    """
                    INSERT OR IGNORE INTO item_example_sources(
                      item_id, position, source_book_code, source_index
                    ) VALUES(?, ?, ?, ?)
                    """,
                    (m["item_id"], position, BOOK_CODE, m["source_index"]),
                )

            conn.execute(
                """
                INSERT INTO word_service_settings(key, value, updated_at)
                VALUES('gwb_missing_entries_added_at', ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (now_utc(), now_utc()),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()

    return {
        "added": len(missing),
        "source_indexes": [m["source_index"] for m in missing],
        "empty_example_count": sum(1 for m in missing if not m["sentence"]),
        "text_already_in_db_count": sum(1 for m in missing if m["text_already_in_db"]),
    }


def verify(db_path: Path, expected_added: int) -> list[str]:
    problems = []
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    total = cur.execute(
        "SELECT count(*) FROM book_entries WHERE book_code=?", (BOOK_CODE,)
    ).fetchone()[0]
    if total != expected_added:
        problems.append(f"GWB book_entries total {total} != expected {expected_added}")
    dupes = cur.execute(
        "SELECT count(*) FROM (SELECT source_index FROM book_entries "
        "WHERE book_code=? GROUP BY source_index HAVING count(*)>1)",
        (BOOK_CODE,),
    ).fetchone()[0]
    if dupes:
        problems.append(f"duplicate source_index rows: {dupes}")
    fk = cur.execute("PRAGMA foreign_key_check").fetchall()
    if fk:
        problems.append(f"foreign key violations: {len(fk)}")
    integrity = cur.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        problems.append(f"integrity check: {integrity}")
    print(f"Verify: GWB book_entries={total}, duplicate source_indexes={dupes}, "
          f"fk_violations={len(fk)}, integrity={integrity}")
    conn.close()
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--green-root", default=str(DEFAULT_GREEN_ROOT))
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db)
    green_root = Path(args.green_root)

    conn = sqlite3.connect(db_path)
    records = read_json(green_root / "data" / "green_word_book_n2_vocab.json")["records"]
    missing = compute_missing(records, conn)
    conn.close()
    print(f"records in JSON: {len(records)} | missing from GWB_N2: {len(missing)}")
    print(
        f"  empty example text: {sum(1 for m in missing if not m['sentence'])} | "
        f"example text already in DB (cross-record duplicates): "
        f"{sum(1 for m in missing if m['text_already_in_db'])}"
    )
    if not missing:
        print("Nothing to add.")
        return 0

    if args.dry_run:
        print("Dry run — no changes made.")
        return 0

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"{db_path}.backup_before_gwb_missing_entries_{ts}"
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(backup)
    src.backup(dst)
    dst.close()
    src.close()
    print(f"DB backup -> {backup}")

    conn = sqlite3.connect(db_path)
    before = conn.execute(
        "SELECT count(*) FROM book_entries WHERE book_code=?", (BOOK_CODE,)
    ).fetchone()[0]
    conn.close()

    summary = add_missing(db_path, green_root)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    problems = verify(db_path, before + len(missing))
    if problems:
        for p in problems:
            print("VERIFY FAILED:", p)
        return 2

    Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
    Path(args.summary).write_text(
        json.dumps({**summary, "db": str(db_path)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
