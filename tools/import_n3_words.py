"""
Import N3Words vocabulary into the shared wordService SQLite database.

The source project has two useful layers:
- canonical word JSON: one row per vocabulary word
- refined listening-deck notes: sentence examples, explanations, and audio

This script merges both into book_code=N3, copies reusable audio into this
repo's clips/n3 folder, and writes a small JSON summary for review.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from merge_gwb_duplicates import restore_provenance_examples


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "wordService" / "data" / "n2vocab.sqlite"
DEFAULT_N3_ROOT = Path(r"D:\n2Prepare\N3Words")
DEFAULT_SUMMARY = PROJECT_ROOT / "output" / "n3_import_summary.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def html_to_markdownish(value: str) -> str:
    text = value or ""
    text = re.sub(r"</p>\s*<hr>\s*<ul>", "\n\n---\n\n", text, flags=re.I)
    text = re.sub(r"<li>(.*?)</li>", lambda m: f"- {m.group(1).strip()}\n", text, flags=re.I | re.S)
    text = re.sub(r"</?(?:p|ul|ol)>", "", text, flags=re.I)
    text = re.sub(r"<strong>(.*?)</strong>", r"**\1**", text, flags=re.I | re.S)
    text = re.sub(r"<em>(.*?)</em>", r"*\1*", text, flags=re.I | re.S)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def sound_filename(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"\[sound:([^\]]+)\]", value)
    return match.group(1) if match else None


def unit_header(unit: dict[str, Any]) -> str:
    return f"Unit {int(unit['unit']):02d} {unit['title']}"


def unit_for_word(word: dict[str, Any], units: dict[int, dict[str, Any]]) -> int:
    if word.get("unit") is not None:
        return int(word["unit"])
    if word.get("_derived_unit") is not None:
        return int(word["_derived_unit"])
    source_index = int(word["id"])
    for number, unit in units.items():
        if not unit.get("id_range"):
            continue
        start, end = unit["id_range"]
        if int(start) <= source_index <= int(end):
            return number
    # N3 canonical rows 221-258 are the "new_u02" supplemental verb block.
    # They are present in words.json but absent from the manifest's Unit 2
    # id_range, while the source audio filename labels them as Unit 2.
    if 221 <= source_index <= 258:
        return 2
    raise KeyError(f"cannot derive unit for N3 word id {source_index}")


def copy_if_present(source: Path, target: Path) -> bool:
    if not source.is_file():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or source.stat().st_size != target.stat().st_size:
        shutil.copy2(source, target)
    return True


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


def load_n3_sources(n3_root: Path) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]], dict[int, list[dict[str, Any]]]]:
    manifest = read_json(n3_root / "data" / "canonical" / "manifest.json")
    words_payload = read_json(n3_root / "data" / "canonical" / "words.json")
    notes_payload = read_json(
        n3_root
        / "generated"
        / "intermediate"
        / "japanese_vocab_listening_refined_extract_check"
        / "notes.json"
    )

    units = {int(item["unit"]): item for item in manifest["units"]}
    words = words_payload["words"] if isinstance(words_payload, dict) else words_payload
    id_to_unit: dict[int, int] = {}
    for unit in manifest["units"]:
        vocab_file = (unit.get("files") or {}).get("vocabulary")
        if not vocab_file:
            continue
        vocab_path = n3_root / "data" / "canonical" / vocab_file
        if not vocab_path.exists():
            vocab_path = n3_root / "data" / vocab_file
        if not vocab_path.exists():
            continue
        payload = read_json(vocab_path)
        unit_words = payload.get("words") if isinstance(payload, dict) else payload
        if not isinstance(unit_words, list):
            continue
        for unit_word in unit_words:
            if isinstance(unit_word, dict) and unit_word.get("id") is not None:
                id_to_unit[int(unit_word["id"])] = int(unit["unit"])
    for word in words:
        if word.get("unit") is None and int(word["id"]) in id_to_unit:
            word["_derived_unit"] = id_to_unit[int(word["id"])]
    examples_by_word: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for note in notes_payload["notes"]:
        word_id = note.get("word_index") or note.get("word_id")
        if not word_id:
            continue
        examples_by_word[int(word_id)].append(note)
    return words, units, examples_by_word


def import_n3(db_path: Path, n3_root: Path, copy_audio: bool) -> dict[str, Any]:
    words, units, examples_by_word = load_n3_sources(n3_root)
    word_audio_source = n3_root / "dist" / "anki" / "mimikara_n3_full_extracted" / "audio" / "words"
    sentence_audio_source = (
        n3_root
        / "generated"
        / "intermediate"
        / "japanese_vocab_listening_refined_extract_check"
        / "audio"
    )
    clips_root = PROJECT_ROOT / "clips"

    conn = connect(db_path)
    copied_word_audio = 0
    copied_sentence_audio = 0
    imported_examples = 0
    missing_word_audio: list[int] = []
    missing_sentence_audio: list[str] = []

    try:
        ensure_import_schema(conn)
        conn.execute("BEGIN")
        conn.execute(
            """
            INSERT INTO books(code, title, notes)
            VALUES('N3', 'N3 語彙トレーニング', 'Imported from D:\\n2Prepare\\N3Words canonical JSON and refined listening deck notes.')
            ON CONFLICT(code) DO UPDATE SET
              title = excluded.title,
              notes = excluded.notes
            """
        )

        for number in sorted(units):
            unit = units[number]
            conn.execute(
                """
                INSERT INTO units(book_code, number, header, title)
                VALUES('N3', ?, ?, ?)
                ON CONFLICT(book_code, number) DO UPDATE SET
                  header = excluded.header,
                  title = excluded.title
                """,
                (number, unit_header(unit), unit["title"]),
            )

        existing_uuid = {
            int(row["source_index"]): row["uuid"]
            for row in conn.execute("SELECT source_index, uuid FROM entries WHERE book_code = 'N3'")
        }
        position_by_unit: dict[int, int] = defaultdict(int)

        for word in sorted(words, key=lambda item: int(item["id"])):
            source_index = int(word["id"])
            unit_number = unit_for_word(word, units)
            position_by_unit[unit_number] += 1
            examples = sorted(
                examples_by_word.get(source_index, []),
                key=lambda item: int(item.get("sentence_number_for_word") or item.get("row_number") or 0),
            )
            main_note = examples[0] if examples else None
            main_fields = (main_note or {}).get("readable_fields", {})
            raw_fields = (main_note or {}).get("fields", {})
            word_audio_name = sound_filename(raw_fields.get("WordAudio")) or f"n2vocab_word_{source_index}.mp3"
            word_clip = f"clips/n3/words/{word_audio_name}"
            if copy_audio:
                if copy_if_present(word_audio_source / word_audio_name, clips_root / "n3" / "words" / word_audio_name):
                    copied_word_audio += 1
                else:
                    missing_word_audio.append(source_index)

            sentence_clip = None
            if main_note and main_note.get("sentence_audio_file"):
                source_name = Path(main_note["sentence_audio_file"]).name
                sentence_clip = f"clips/n3/sentences/{source_name}"
                if copy_audio:
                    if copy_if_present(sentence_audio_source / source_name, clips_root / "n3" / "sentences" / source_name):
                        copied_sentence_audio += 1
                    else:
                        missing_sentence_audio.append(source_name)

            translations = word.get("translations") or {}
            meaning_en = translations.get("en") or word.get("english") or ""
            meaning_zh = translations.get("zh") or ""
            reading = word.get("reading_kana") or word.get("reading") or ""
            row_uuid = existing_uuid.get(source_index) or str(uuid.uuid5(uuid.NAMESPACE_URL, f"n2prepare:N3:{source_index}"))
            conn.execute(
                """
                INSERT INTO entries(
                  uuid, book_code, unit_number, source_index, position,
                  kanji, reading, verb_pattern, meaning_en, meaning_zh,
                  sentence, explanation_md, word_clip, sentence_clip
                )
                VALUES(?, 'N3', ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)
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
                    unit_number,
                    source_index,
                    position_by_unit[unit_number],
                    word.get("kanji") or "",
                    reading,
                    meaning_en,
                    meaning_zh,
                    main_fields.get("ExampleSentence") or "",
                    html_to_markdownish(raw_fields.get("SentenceExplanation") or ""),
                    word_clip,
                    sentence_clip,
                ),
            )
            entry_id = conn.execute(
                "SELECT entry_id FROM entries WHERE book_code = 'N3' AND source_index = ?",
                (source_index,),
            ).fetchone()["entry_id"]
            conn.execute("DELETE FROM entry_examples WHERE entry_id = ?", (entry_id,))

            for position, note in enumerate(examples):
                fields = note.get("readable_fields", {})
                raw_note_fields = note.get("fields", {})
                audio_clip = None
                if note.get("sentence_audio_file"):
                    source_name = Path(note["sentence_audio_file"]).name
                    audio_clip = f"clips/n3/sentences/{source_name}"
                    if position != 0 and copy_audio:
                        if copy_if_present(sentence_audio_source / source_name, clips_root / "n3" / "sentences" / source_name):
                            copied_sentence_audio += 1
                        else:
                            missing_sentence_audio.append(source_name)
                conn.execute(
                    """
                    INSERT INTO entry_examples(entry_id, position, kind, text, translation_en, translation_zh, explanation_md, audio_clip)
                    VALUES(?,?,?,?,?,?,?,?)
                    """,
                    (
                        entry_id,
                        position,
                        "main_sentence" if position == 0 else "example_sentence",
                        fields.get("ExampleSentence") or "",
                        fields.get("SentEN") or "",
                        "",
                        html_to_markdownish(raw_note_fields.get("SentenceExplanation") or ""),
                        audio_clip,
                    ),
                )
                imported_examples += 1

        # N3 import replaces each entry's examples. Rehydrate the separately
        # preserved GWB examples before committing the rebuilt book.
        restored_gwb = restore_provenance_examples(conn, "N3")
        conn.execute(
            """
            INSERT INTO word_service_settings(key, value, updated_at)
            VALUES('n3_import_source', ?, ?)
            ON CONFLICT(key) DO UPDATE SET
              value = excluded.value,
              updated_at = excluded.updated_at
            """,
            (str(n3_root), now_utc()),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    return {
        "db": str(db_path),
        "source": str(n3_root),
        "words_seen": len(words),
        "words_imported": len(words),
        "examples_imported": imported_examples,
        "words_with_examples": sum(1 for word in words if examples_by_word.get(int(word["id"]))),
        "units_imported": len(units),
        "copied_word_audio": copied_word_audio,
        "copied_sentence_audio": copied_sentence_audio,
        "missing_word_audio_count": len(set(missing_word_audio)),
        "missing_word_audio_ids": sorted(set(missing_word_audio))[:80],
        "missing_sentence_audio_count": len(set(missing_sentence_audio)),
        "missing_sentence_audio_files": sorted(set(missing_sentence_audio))[:80],
        "restored_gwb_merge": restored_gwb,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB), help="wordService SQLite database")
    parser.add_argument("--n3-root", default=str(DEFAULT_N3_ROOT), help="N3Words project root")
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY), help="summary JSON output")
    parser.add_argument("--no-copy-audio", action="store_true", help="only update SQLite rows")
    args = parser.parse_args()

    summary = import_n3(Path(args.db), Path(args.n3_root), copy_audio=not args.no_copy_audio)
    summary_path = Path(args.summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
