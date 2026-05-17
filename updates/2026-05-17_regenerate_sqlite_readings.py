#!/usr/bin/env python3
"""
Regenerate SQLite readings for displayed kanji headwords.

`vocabulary.json` has been retired; the live word source is
`output/n2vocab.sqlite`. This script updates `entries.reading` in place for
N2 rows whose displayed headword contains kanji.

Reading source order:
  1. OCR raw header token, but only when the same raw header also contains the
     displayed headword. This preserves book-specific readings such as 空=から.
  2. Local fugashi/unidic_lite reading generated from the displayed headword.

The script also clears `verb_pattern` for all N2 entries. The UI no longer
displays that field, but clearing it prevents old parser markers from leaking
into future exports.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import jaconv
from fugashi import Tagger
import unidic_lite


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "output" / "n2vocab.sqlite"
JSON_DIR = PROJECT_ROOT / "json"
REPORT_PATH = PROJECT_ROOT / "output" / "reading_regen_2026-05-17.json"

KANJI_RE = re.compile(r"[一-龯]")
HEADER_TOKEN_RE = re.compile(r"(?<!\d)(\d{1,4})\s+([^\s]+)")
BAD_READING_CHARS_RE = re.compile(r"[一-龯A-Za-z0-9]")

# unidic reads a few short headwords oddly when no context is available.
READING_OVERRIDES_BY_INDEX = {
    755: "つく",  # 就く
    # These rows have visibly damaged displayed headwords, but the existing
    # reading still matches the intended vocabulary item better than a literal
    # dictionary reading of the damaged surface.
    882: "てきかくな",  # intended 的確な, stored surface is currently 的な
    996: "すすぐ",     # intended すすぐ/濯ぐ, stored surface is currently 洗す
    1019: "すする",    # intended すする, stored surface is currently 吸する
    1088: "くやむ",    # stored surface has an OCR-leading ラ
    1090: "うやまう",  # stored surface has an OCR-leading ラ
}


@dataclass
class Entry:
    entry_id: int
    source_index: int
    headword: str
    reading: str
    verb_pattern: str | None


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def strip_usage_markers(text: str) -> str:
    s = (text or "").strip()
    s = s.replace("（", "(").replace("）", ")")
    s = s.replace("〈", "").replace("〉", "")
    s = re.sub(r"^[\s/／]*[ガヲ]+", "", s)
    s = re.sub(r"[ガヲ]?(?:\([ガヲ/／]+\))?スル$", "", s)
    return s.strip()


def headword_needles(headword: str) -> list[str]:
    """
    Return kanji-bearing substrings that should appear after an OCR header's
    reading token if that header is really for this DB row.
    """
    cleaned = strip_usage_markers(headword)
    chunks = re.split(r"[/／\[\]()<>\s]+", cleaned)
    needles: list[str] = []
    for chunk in chunks:
        chunk = strip_usage_markers(chunk)
        if KANJI_RE.search(chunk):
            needles.append(compact(chunk))
    return sorted(set(needles), key=len, reverse=True)


def raw_reading_candidates() -> dict[int, list[tuple[str, str]]]:
    candidates: dict[int, list[tuple[str, str]]] = {}
    for path in sorted(JSON_DIR.glob("page_*.json")):
        obj = json.loads(path.read_text(encoding="utf-8"))
        entry_numbers = {
            int(item["number"])
            for item in obj.get("entries") or []
            if item.get("number") is not None
        }
        if not entry_numbers:
            continue
        raw_text = obj.get("raw_text") or ""
        for match in HEADER_TOKEN_RE.finditer(raw_text):
            source_index = int(match.group(1))
            if source_index not in entry_numbers:
                continue
            token = match.group(2)
            if BAD_READING_CHARS_RE.search(token):
                continue
            if not re.search(r"[ぁ-ゖァ-ヴー]", token):
                continue
            snippet = raw_text[match.start(): match.start() + 120].replace("\n", " ")
            candidates.setdefault(source_index, []).append((token, snippet))
    return candidates


def validated_raw_reading(entry: Entry, candidates: dict[int, list[tuple[str, str]]]) -> tuple[str, str] | None:
    needles = headword_needles(entry.headword)
    if not needles:
        return None
    for token, snippet in candidates.get(entry.source_index, []):
        snippet_compact = compact(strip_usage_markers(snippet))
        if any(needle and needle in snippet_compact for needle in needles):
            return normalize_reading_token(token), snippet
    return None


def normalize_reading_token(token: str) -> str:
    return jaconv.kata2hira((token or "").strip())


def surfaces_for_generation(headword: str) -> list[str]:
    s = strip_usage_markers(headword)

    # Prefer the explicit kana spelling when a headword is written like
    # `なにもかも (何もかも)` or `おそらく/恐らく`.
    leading_kana = re.match(r"^([ぁ-ゖァ-ヴー（）()・/／]+)\s*(?:[/／]|\()", s)
    if leading_kana and KANJI_RE.search(s[leading_kana.end():]):
        kana = leading_kana.group(1).strip()
        if kana:
            return [kana]

    parts = [part for part in re.split(r"[/／]", s) if part.strip()]
    if parts:
        return [strip_usage_markers(part) for part in parts]
    return [s]


def generated_reading(headword: str, tagger: Tagger) -> str:
    readings: list[str] = []
    for surface in surfaces_for_generation(headword):
        surface_readings: list[str] = []
        for word in tagger(surface):
            reading = getattr(word.feature, "kana", None) or getattr(word.feature, "pron", None)
            surface_readings.append(reading or word.surface)
        readings.append(jaconv.kata2hira("".join(surface_readings)))
    return "／".join(reading for reading in readings if reading)


def load_entries(conn: sqlite3.Connection) -> list[Entry]:
    rows = conn.execute(
        """
        SELECT entry_id, source_index, kanji, headword_text, reading, verb_pattern
          FROM entries
         WHERE book_code = 'N2'
         ORDER BY source_index
        """
    ).fetchall()
    entries: list[Entry] = []
    for row in rows:
        headword = row["headword_text"] or row["kanji"] or ""
        entries.append(
            Entry(
                entry_id=row["entry_id"],
                source_index=row["source_index"],
                headword=headword,
                reading=row["reading"] or "",
                verb_pattern=row["verb_pattern"],
            )
        )
    return entries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args()

    tagger = Tagger(f'-d "{unidic_lite.DICDIR}"')
    raw_candidates = raw_reading_candidates()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    changes: list[dict] = []
    cleared_patterns = 0
    considered = 0
    try:
        entries = load_entries(conn)
        if not args.dry_run:
            conn.execute("BEGIN")
        for entry in entries:
            has_kanji = bool(KANJI_RE.search(entry.headword))
            new_reading = entry.reading
            source = "unchanged-no-kanji"
            snippet = ""

            if has_kanji:
                considered += 1
                raw = validated_raw_reading(entry, raw_candidates)
                if raw:
                    new_reading, snippet = raw
                    source = "ocr-header"
                elif entry.source_index in READING_OVERRIDES_BY_INDEX:
                    new_reading = READING_OVERRIDES_BY_INDEX[entry.source_index]
                    source = "manual-override"
                else:
                    new_reading = generated_reading(entry.headword, tagger)
                    source = "fugashi"

            should_clear_pattern = entry.verb_pattern is not None
            if should_clear_pattern:
                cleared_patterns += 1

            if new_reading != entry.reading or should_clear_pattern:
                changes.append({
                    "index": entry.source_index,
                    "headword": entry.headword,
                    "old_reading": entry.reading,
                    "new_reading": new_reading,
                    "old_verb_pattern": entry.verb_pattern,
                    "source": source,
                    "raw_snippet": snippet,
                })
                if not args.dry_run:
                    conn.execute(
                        """
                        UPDATE entries
                           SET reading = ?, verb_pattern = NULL
                         WHERE entry_id = ?
                        """,
                        (new_reading, entry.entry_id),
                    )

        if not args.dry_run:
            conn.execute("COMMIT")
    except Exception:
        if not args.dry_run:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    report = {
        "dry_run": args.dry_run,
        "kanji_entries_considered": considered,
        "changed_rows": len(changes),
        "verb_patterns_cleared": cleared_patterns,
        "changes": changes,
    }
    if not args.dry_run:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    mode = "would update" if args.dry_run else "updated"
    print(f"{mode} {len(changes)} rows")
    print(f"kanji entries considered: {considered}")
    print(f"verb_pattern values cleared: {cleared_patterns}")
    if not args.dry_run:
        print(f"report: {args.report}")


if __name__ == "__main__":
    main()
