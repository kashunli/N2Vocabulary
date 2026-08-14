"""Import the accepted Mimikara N1 vocabulary and CD clips into wordService.

The source project remains read-only. This importer writes both the legacy
book-scoped tables and the canonical shared-item tables so the Rust service and
SQLite-backed Anki exporter see the same N1 book immediately.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_DIR = PROJECT_ROOT / "db"
if str(DB_DIR) not in sys.path:
    sys.path.insert(0, str(DB_DIR))

from migrate import apply_all  # type: ignore[import-not-found]  # noqa: E402


BOOK_CODE = "N1"
BOOK_TITLE = "耳から覚える N1語彙トレーニング"
SOURCE_TITLE = "N1語彙トレーニング"
EXPECTED_ENTRIES = 1170
DEFAULT_SOURCE = Path(r"D:\n2Prepare\minikaraWordN1")
DEFAULT_DB = PROJECT_ROOT / "wordService" / "data" / "n2vocab.sqlite"
DEFAULT_CLIPS = PROJECT_ROOT / "clips"
DEFAULT_SUMMARY = PROJECT_ROOT / "output" / "mimikara_n1_import_summary.json"

# Keep the established book markers used by the existing N2/N2_1500 data.
# `関連` is explicit because a broad related concept is neither a synonym nor
# a compound and should not be forced into one of those narrower categories.
RELATION_FIELDS = (
    ("compounds", "合"),
    ("collocations", "連"),
    ("synonyms", "類"),
    ("antonyms", "対"),
    ("related", "関連"),
    ("idioms", "慣"),
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def stable_uuid(kind: str, source_index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"n2prepare:{kind}:{BOOK_CODE}:{source_index}"))


def normalize(value: str | None) -> str:
    return "".join((value or "").split())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_payload(source_root: Path) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    vocabulary = load_json(source_root / "data" / "processed" / "vocabulary.json")
    audio = load_json(source_root / "data" / "processed" / "audio_clips" / "clip_manifest.json")
    validation = load_json(source_root / "data" / "processed" / "audio_clips" / "validation_report.json")
    entries = [dict(entry) for entry in vocabulary["entries"]]
    track_manifest = load_json(
        source_root / "data" / "intermediate" / "audio" / "proposed_track_manifest.json"
    )
    unit_by_index: dict[int, int] = {}
    for track in track_manifest["tracks"]:
        match = re.search(r"(?:^|/)Unit(\d+)", str(track["audio"]).replace("\\", "/"))
        if not match:
            raise ValueError(f"cannot derive N1 unit from accepted track path: {track['audio']}")
        unit = int(match.group(1))
        for index in range(int(track["index_start"]), int(track["index_end"]) + 1):
            unit_by_index[index] = unit
    if vocabulary.get("entry_count") != EXPECTED_ENTRIES or len(entries) != EXPECTED_ENTRIES:
        raise ValueError("N1 source must contain exactly 1,170 canonical entries")
    if audio.get("status") != "accepted" or validation.get("status") != "accepted":
        raise ValueError("N1 audio dataset must be accepted before import")
    if audio.get("word_clip_count") != EXPECTED_ENTRIES or audio.get("sentence_clip_count") != EXPECTED_ENTRIES:
        raise ValueError("N1 audio manifest must contain 1,170 clips of each kind")
    clips: dict[int, dict[str, Any]] = defaultdict(dict)
    for clip in audio["clips"]:
        clips[int(clip["index"])][str(clip["kind"])] = clip
    for expected, entry in enumerate(entries, start=1):
        if int(entry["index"]) != expected:
            raise ValueError(f"N1 source index discontinuity at {expected}")
        if set(clips[expected]) != {"word", "sentence"}:
            raise ValueError(f"N1 index {expected} lacks accepted word/sentence audio")
        if not entry["headword"] or not entry["reading"] or not entry["examples"]:
            raise ValueError(f"N1 index {expected} lacks required learner content")
        if expected not in unit_by_index:
            raise ValueError(f"accepted N1 track manifest does not cover index {expected}")
        entry["_import_unit"] = unit_by_index[expected]
    return entries, clips


def source_reference(entry: dict[str, Any], track: str) -> dict[str, Any]:
    """Return structured provenance for one accepted N1 source occurrence."""

    return {
        "title": SOURCE_TITLE,
        "page": int(entry["page"]),
        "cd_track": track,
    }


def source_notes_markdown(entry: dict[str, Any]) -> str:
    """Keep source-specific usage/notes separate from sentence explanations."""

    lines: list[str] = []
    fields = [
        ("Usage", entry.get("usage") and [entry["usage"]]),
        ("Notes", entry.get("notes")),
    ]
    for label, values in fields:
        clean = [str(value).strip() for value in (values or []) if str(value).strip()]
        if clean:
            lines.append(f"- **{label}:** {', '.join(clean)}")
    return "\n".join(lines)


def structured_terms(entry: dict[str, Any]) -> list[tuple[str, str]]:
    """Return one normalized `(category, term)` row per source relationship."""

    terms: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for field, category in RELATION_FIELDS:
        for raw_value in entry.get(field) or []:
            term = str(raw_value).strip()
            key = (category, normalize(term))
            if term and key not in seen:
                seen.add(key)
                terms.append((category, term))
    return terms


def remove_previous_n1_terms(conn: sqlite3.Connection, item_id: int, source_index: int) -> int:
    """Remove this source row's old term links and unreferenced term records."""

    positions = [
        int(row["position"])
        for row in conn.execute(
            """
            SELECT p.position
            FROM item_example_sources p
            JOIN item_examples ex
              ON ex.item_id=p.item_id AND ex.position=p.position
            WHERE p.item_id=? AND p.source_book_code=? AND p.source_index=?
              AND ex.kind='related_term'
            """,
            (item_id, BOOK_CODE, source_index),
        )
    ]
    if not positions:
        return 0
    placeholders = ",".join("?" for _ in positions)
    conn.execute(
        f"DELETE FROM item_example_sources WHERE item_id=? AND source_book_code=? AND source_index=? AND position IN ({placeholders})",
        (item_id, BOOK_CODE, source_index, *positions),
    )
    # Preserve rows still linked to another source.
    result = conn.execute(
        f"""
        DELETE FROM item_examples
        WHERE item_id=? AND position IN ({placeholders})
          AND NOT EXISTS (
            SELECT 1 FROM item_example_sources p
            WHERE p.item_id=item_examples.item_id AND p.position=item_examples.position
          )
        """,
        (item_id, *positions),
    )
    return result.rowcount


def previous_n1_term_translations(
    conn: sqlite3.Connection, item_id: int, source_index: int
) -> dict[tuple[str, str], str]:
    """Capture generated English before idempotent term reconciliation."""

    return {
        (str(row["category"] or ""), normalize(str(row["text"]))): str(row["translation_en"])
        for row in conn.execute(
            """
            SELECT ex.category, ex.text, ex.translation_en
            FROM item_example_sources p
            JOIN item_examples ex
              ON ex.item_id=p.item_id AND ex.position=p.position
            WHERE p.item_id=? AND p.source_book_code=? AND p.source_index=?
              AND ex.kind='related_term'
              AND TRIM(COALESCE(ex.translation_en, ''))<>''
            """,
            (item_id, BOOK_CODE, source_index),
        )
    }


def target_clip_paths(index: int, _word_source: Path) -> tuple[str, str]:
    return (
        f"clips/n1/words/Word{index:04d}.mp3",
        f"clips/n1/sentences/Sentence{index:04d}.mp3",
    )


def exact_item(conn: sqlite3.Connection, entry: dict[str, Any]) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT item_id FROM vocabulary_items
        WHERE TRIM(kanji)=? AND TRIM(COALESCE(reading, ''))=?
        """,
        (entry["headword"].strip(), entry["reading"].strip()),
    ).fetchone()


def ensure_item(conn: sqlite3.Connection, entry: dict[str, Any], word_clip: str) -> tuple[int, bool]:
    existing = exact_item(conn, entry)
    if existing:
        return int(existing["item_id"]), False
    conn.execute(
        """
        INSERT INTO vocabulary_items(
          uuid, kanji, reading, verb_pattern, meaning_en, meaning_zh,
          explanation_md, word_clip
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            stable_uuid("item", int(entry["index"])),
            entry["headword"],
            entry["reading"],
            entry.get("usage") or None,
            entry["meaning"].get("english") or None,
            entry["meaning"].get("chinese") or None,
            "",
            word_clip,
        ),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0]), True


def import_book(
    db_path: Path,
    source_root: Path,
    clips_root: Path,
    *,
    limit: int | None = None,
) -> dict[str, Any]:
    entries, audio = source_payload(source_root)
    selected = entries[:limit] if limit else entries
    apply_all(db_path)
    conn = connect(db_path)
    counters: Counter[str] = Counter()
    copy_jobs: list[tuple[Path, Path]] = []
    position_by_unit: defaultdict[int, int] = defaultdict(int)
    try:
        conn.execute("BEGIN")
        conn.execute("PRAGMA defer_foreign_keys = ON")
        conn.execute(
            """
            INSERT INTO books(code, title, notes) VALUES(?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET title=excluded.title, notes=excluded.notes
            """,
            (BOOK_CODE, BOOK_TITLE, f"Imported from accepted artifacts in {source_root}"),
        )
        for unit in sorted({int(entry["_import_unit"]) for entry in selected}):
            conn.execute(
                """
                INSERT INTO units(book_code, number, header, title) VALUES(?, ?, ?, ?)
                ON CONFLICT(book_code, number) DO UPDATE SET header=excluded.header, title=excluded.title
                """,
                (BOOK_CODE, unit, f"Unit {unit:02d}", f"Unit {unit}"),
            )

        for entry in selected:
            index = int(entry["index"])
            unit = int(entry["_import_unit"])
            position_by_unit[unit] += 1
            word_source = source_root / "data" / "processed" / "audio_clips" / audio[index]["word"]["file"]
            sentence_source = source_root / "data" / "processed" / "audio_clips" / audio[index]["sentence"]["file"]
            if not word_source.is_file() or not sentence_source.is_file():
                raise FileNotFoundError(f"accepted N1 media missing for index {index}")
            word_clip, sentence_clip = target_clip_paths(index, word_source)
            copy_jobs.extend(
                [
                    (word_source, clips_root / Path(word_clip).relative_to("clips")),
                    (sentence_source, clips_root / Path(sentence_clip).relative_to("clips")),
                ]
            )
            track = str(audio[index]["word"]["track"])
            reference = source_reference(entry, track)
            source_notes = source_notes_markdown(entry)
            item_id, created = ensure_item(conn, entry, word_clip)
            counters["new_items" if created else "exact_item_matches"] += 1
            row_uuid = stable_uuid("entry", index)
            conn.execute(
                """
                INSERT INTO entries(
                  uuid, book_code, unit_number, source_index, position,
                  kanji, reading, verb_pattern, meaning_en, meaning_zh,
                  sentence, explanation_md, word_clip, sentence_clip
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_code, source_index) DO UPDATE SET
                  unit_number=excluded.unit_number, position=excluded.position,
                  kanji=excluded.kanji, reading=excluded.reading,
                  verb_pattern=excluded.verb_pattern, meaning_en=excluded.meaning_en,
                  meaning_zh=excluded.meaning_zh, sentence=excluded.sentence,
                  explanation_md=excluded.explanation_md, word_clip=excluded.word_clip,
                  sentence_clip=excluded.sentence_clip
                """,
                (
                    row_uuid, BOOK_CODE, unit, index, position_by_unit[unit],
                    entry["headword"], entry["reading"], entry.get("usage") or None,
                    entry["meaning"].get("english") or None,
                    entry["meaning"].get("chinese") or None,
                    entry["examples"][0], "", word_clip, sentence_clip,
                ),
            )
            entry_id = int(
                conn.execute(
                    "SELECT entry_id FROM entries WHERE book_code=? AND source_index=?",
                    (BOOK_CODE, index),
                ).fetchone()["entry_id"]
            )
            conn.execute(
                """
                INSERT INTO book_entries(
                  entry_id, item_id, uuid, book_code, unit_number, source_index,
                  position, sentence, explanation_md, sentence_clip, word_clip,
                  verb_pattern, meaning_en, meaning_zh
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_code, source_index) DO UPDATE SET
                  item_id=excluded.item_id, unit_number=excluded.unit_number,
                  position=excluded.position, sentence=excluded.sentence,
                  explanation_md=excluded.explanation_md,
                  sentence_clip=excluded.sentence_clip, word_clip=excluded.word_clip,
                  verb_pattern=excluded.verb_pattern, meaning_en=excluded.meaning_en,
                  meaning_zh=excluded.meaning_zh,
                  updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                """,
                (
                    entry_id, item_id, row_uuid, BOOK_CODE, unit, index,
                    position_by_unit[unit], entry["examples"][0], "",
                    sentence_clip, word_clip, entry.get("usage") or None,
                    entry["meaning"].get("english") or None,
                    entry["meaning"].get("chinese") or None,
                ),
            )
            conn.execute("DELETE FROM entry_examples WHERE entry_id=?", (entry_id,))
            saved_term_translations = previous_n1_term_translations(conn, item_id, index)
            counters["old_structured_terms_removed"] += remove_previous_n1_terms(conn, item_id, index)
            for example_position, text in enumerate(entry["examples"]):
                conn.execute(
                    """
                    INSERT INTO entry_examples(
                      entry_id, position, kind, text, audio_clip
                    ) VALUES(?, ?, ?, ?, ?)
                    """,
                    (
                        entry_id,
                        example_position,
                        "main_sentence" if example_position == 0 else "example_sentence",
                        text,
                        sentence_clip if example_position == 0 else None,
                    ),
                )

                existing_example = conn.execute(
                    """
                    SELECT position FROM item_examples
                    WHERE item_id=? AND TRIM(text)=? AND kind<>'related_term'
                    ORDER BY position LIMIT 1
                    """,
                    (item_id, text.strip()),
                ).fetchone()
                if existing_example:
                    item_position = int(existing_example["position"])
                    counters["examples_reused"] += 1
                else:
                    maximum = conn.execute(
                        "SELECT MAX(position) FROM item_examples WHERE item_id=?",
                        (item_id,),
                    ).fetchone()[0]
                    item_position = int(maximum) + 1 if maximum is not None else 0
                    kind = "main_sentence" if item_position == 0 and example_position == 0 else "example_sentence"
                    conn.execute(
                        """
                        INSERT INTO item_examples(item_id, position, kind, text, audio_clip)
                        VALUES(?, ?, ?, ?, ?)
                        """,
                        (item_id, item_position, kind, text, sentence_clip if kind == "main_sentence" else None),
                    )
                    counters["examples_added"] += 1

                conn.execute(
                    """
                    INSERT OR IGNORE INTO item_example_sources(item_id, position, source_book_code, source_index)
                    VALUES(?, ?, ?, ?)
                    """,
                    (item_id, item_position, BOOK_CODE, index),
                )

            for term_offset, (category, term) in enumerate(structured_terms(entry)):
                conn.execute(
                    """
                    INSERT INTO entry_examples(
                      entry_id, position, kind, text, category
                    ) VALUES(?, ?, 'related_term', ?, ?)
                    """,
                    (entry_id, len(entry["examples"]) + term_offset, term, category),
                )

                existing_term = conn.execute(
                    """
                    SELECT position FROM item_examples
                    WHERE item_id=? AND kind='related_term' AND TRIM(text)=?
                      AND COALESCE(category, '')=?
                    ORDER BY position LIMIT 1
                    """,
                    (item_id, term.strip(), category),
                ).fetchone()
                if existing_term:
                    item_position = int(existing_term["position"])
                    conn.execute(
                        """
                        UPDATE item_examples SET category=?
                        WHERE item_id=? AND position=?
                          AND TRIM(COALESCE(category, ''))=''
                        """,
                        (category, item_id, item_position),
                    )
                    counters["structured_terms_reused"] += 1
                else:
                    maximum = conn.execute(
                        "SELECT MAX(position) FROM item_examples WHERE item_id=?",
                        (item_id,),
                    ).fetchone()[0]
                    item_position = int(maximum) + 1 if maximum is not None else 0
                    conn.execute(
                        """
                        INSERT INTO item_examples(item_id, position, kind, text, category)
                        VALUES(?, ?, 'related_term', ?, ?)
                        """,
                        (item_id, item_position, term, category),
                    )
                    counters["structured_terms_added"] += 1

                conn.execute(
                    """
                    INSERT OR IGNORE INTO item_example_sources(
                      item_id, position, source_book_code, source_index
                    ) VALUES(?, ?, ?, ?)
                    """,
                    (item_id, item_position, BOOK_CODE, index),
                )
                saved_translation = saved_term_translations.get((category, normalize(term)))
                if saved_translation:
                    conn.execute(
                        """
                        UPDATE item_examples SET translation_en=?
                        WHERE item_id=? AND position=?
                          AND TRIM(COALESCE(translation_en, ''))=''
                        """,
                        (saved_translation, item_id, item_position),
                    )

            # Keep the compatibility table synchronized with canonical English
            # after sentence/term rows have been reconciled.
            conn.execute(
                """
                UPDATE entry_examples
                   SET translation_en = COALESCE((
                     SELECT ex.translation_en FROM item_examples ex
                     WHERE ex.item_id=?
                       AND COALESCE(ex.category, '')=COALESCE(entry_examples.category, '')
                       AND TRIM(ex.text)=TRIM(entry_examples.text)
                       AND TRIM(COALESCE(ex.translation_en, ''))<>''
                     ORDER BY ex.position LIMIT 1
                   ), translation_en)
                 WHERE entry_id=?
                """,
                (item_id, entry_id),
            )

            conn.execute(
                """
                INSERT INTO item_source_notes(
                  item_id, source_book_code, source_entry_uuid, source_index,
                  source_reading, source_meaning_en, source_meaning_zh,
                  source_title, source_page, source_cd_track, source_notes_md,
                  source_explanation_md, source_sentence, source_word_clip,
                  source_sentence_clip
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(item_id, source_book_code, source_index) DO UPDATE SET
                  source_entry_uuid=excluded.source_entry_uuid,
                  source_reading=excluded.source_reading,
                  source_meaning_en=excluded.source_meaning_en,
                  source_meaning_zh=excluded.source_meaning_zh,
                  source_title=excluded.source_title,
                  source_page=excluded.source_page,
                  source_cd_track=excluded.source_cd_track,
                  source_notes_md=excluded.source_notes_md,
                  source_explanation_md=NULL,
                  source_sentence=excluded.source_sentence,
                  source_word_clip=excluded.source_word_clip,
                  source_sentence_clip=excluded.source_sentence_clip
                """,
                (
                    item_id, BOOK_CODE, row_uuid, index, entry["reading"],
                    entry["meaning"].get("english") or None,
                    entry["meaning"].get("chinese") or None,
                    reference["title"], reference["page"], reference["cd_track"],
                    source_notes, None, entry["examples"][0], word_clip, sentence_clip,
                ),
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    copied = reused = 0
    for source, target in copy_jobs:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.stat().st_size != source.stat().st_size or sha256(target) != sha256(source):
                raise ValueError(f"existing target media differs from accepted source: {target}")
            reused += 1
        else:
            shutil.copy2(source, target)
            copied += 1

    conn = connect(db_path)
    try:
        health = {
            "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
            "foreign_key_check_rows": len(conn.execute("PRAGMA foreign_key_check").fetchall()),
        }
        counts = {
            "entries": conn.execute("SELECT COUNT(*) FROM entries WHERE book_code=?", (BOOK_CODE,)).fetchone()[0],
            "book_entries": conn.execute("SELECT COUNT(*) FROM book_entries WHERE book_code=?", (BOOK_CODE,)).fetchone()[0],
            "units": conn.execute("SELECT COUNT(*) FROM units WHERE book_code=?", (BOOK_CODE,)).fetchone()[0],
        }
    finally:
        conn.close()
    return {
        "book_code": BOOK_CODE,
        "book_title": BOOK_TITLE,
        "source": str(source_root),
        "db": str(db_path),
        "selected_entries": len(selected),
        "full_import": limit is None,
        "counts": counts,
        "new_items": counters["new_items"],
        "exact_item_matches": counters["exact_item_matches"],
        "examples_added": counters["examples_added"],
        "examples_reused": counters["examples_reused"],
        "structured_terms_added": counters["structured_terms_added"],
        "structured_terms_reused": counters["structured_terms_reused"],
        "old_structured_terms_removed": counters["old_structured_terms_removed"],
        "media_copied": copied,
        "media_reused": reused,
        "health": health,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--clips-root", type=Path, default=DEFAULT_CLIPS)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    summary = import_book(args.db, args.source_root, args.clips_root, limit=args.limit)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
