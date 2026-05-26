"""Create and audit flat canonical word/sentence clip paths.

The cutting workflow keeps track-level folders because they are useful repair
evidence: each folder has its own `pairs.json` and mirrors the source track.
The study service, however, only needs a stable lookup by vocabulary index.
This script bridges those two needs by copying canonical aliases into:

    clips/words/word{entry_id}.mp3
    clips/sentences/sentence{entry_id}.mp3

Run without flags for a read-only audit. Add `--apply` to copy the flat files,
and add `--migrate-db` to update SQLite references after the flat files exist.
"""

from __future__ import annotations

import argparse
import filecmp
import re
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORD_RE = re.compile(r"word(\d+)(?:-deduced)?\.mp3$")
SENTENCE_RE = re.compile(r"sentence(\d+)(?:-deduced)?\.mp3$")
SKIP_SOURCE_DIRS = {"words", "sentences", "generated_sentences"}


@dataclass(frozen=True)
class ClipIndex:
    word_sources: dict[int, Path]
    sentence_sources: dict[int, Path]
    duplicate_words: dict[int, list[Path]]
    duplicate_sentences: dict[int, list[Path]]


@dataclass(frozen=True)
class EntryRow:
    entry_id: int
    word_clip: str | None
    sentence_clip: str | None
    main_audio_clip: str | None


def posix_rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_source_clip(path: Path, clips_root: Path) -> bool:
    rel_parts = path.relative_to(clips_root).parts
    return not any(part in SKIP_SOURCE_DIRS for part in rel_parts)


def collect_kind(clips_root: Path, regex: re.Pattern[str]) -> tuple[dict[int, Path], dict[int, list[Path]]]:
    by_index: dict[int, list[Path]] = {}
    for path in clips_root.rglob("*.mp3"):
        if not is_source_clip(path, clips_root):
            continue
        match = regex.fullmatch(path.name)
        if not match:
            continue
        by_index.setdefault(int(match.group(1)), []).append(path)

    chosen: dict[int, Path] = {}
    duplicates: dict[int, list[Path]] = {}
    for index, paths in by_index.items():
        ordered = sorted(paths, key=lambda p: p.as_posix())
        if len(ordered) > 1:
            duplicates[index] = ordered
        else:
            chosen[index] = ordered[0]
    return chosen, duplicates


def collect_clips(clips_root: Path) -> ClipIndex:
    word_sources, duplicate_words = collect_kind(clips_root, WORD_RE)
    sentence_sources, duplicate_sentences = collect_kind(clips_root, SENTENCE_RE)
    return ClipIndex(word_sources, sentence_sources, duplicate_words, duplicate_sentences)


def load_entries(db_path: Path) -> list[EntryRow]:
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT e.entry_id, e.word_clip, e.sentence_clip, ex.audio_clip AS main_audio_clip
            FROM entries e
            LEFT JOIN entry_examples ex
              ON ex.entry_id = e.entry_id
             AND ex.position = 0
            WHERE e.book_code = 'N2'
            ORDER BY e.entry_id
            """
        ).fetchall()
        return [
            EntryRow(
                entry_id=int(row["entry_id"]),
                word_clip=row["word_clip"],
                sentence_clip=row["sentence_clip"],
                main_audio_clip=row["main_audio_clip"],
            )
            for row in rows
        ]
    finally:
        conn.close()


def canonical_word_path(entry_id: int) -> str:
    return f"clips/words/word{entry_id}.mp3"


def canonical_sentence_path(entry_id: int) -> str:
    return f"clips/sentences/sentence{entry_id}.mp3"


def normalize_stored_path(value: str | None) -> str:
    return (value or "").replace("\\", "/").lstrip("/")


def existing_project_path(value: str | None) -> Path | None:
    normalized = normalize_stored_path(value)
    if normalized.startswith("output/clips/"):
        normalized = normalized.removeprefix("output/")
    if not normalized.startswith("clips/"):
        return None
    return ROOT / normalized


def audit(entries: list[EntryRow], clips: ClipIndex, clips_root: Path) -> dict[str, list[str]]:
    entry_ids = [row.entry_id for row in entries]
    issues: dict[str, list[str]] = {
        "missing_word_sources": [],
        "missing_sentence_sources": [],
        "duplicate_word_sources": [],
        "duplicate_sentence_sources": [],
        "noncanonical_db_paths": [],
        "stale_db_paths": [],
        "missing_flat_files": [],
    }

    for entry_id in entry_ids:
        if entry_id not in clips.word_sources:
            issues["missing_word_sources"].append(str(entry_id))
        if entry_id not in clips.sentence_sources:
            issues["missing_sentence_sources"].append(str(entry_id))

    for entry_id, paths in clips.duplicate_words.items():
        issues["duplicate_word_sources"].append(
            f"{entry_id}: " + ", ".join(posix_rel(path) for path in paths)
        )
    for entry_id, paths in clips.duplicate_sentences.items():
        issues["duplicate_sentence_sources"].append(
            f"{entry_id}: " + ", ".join(posix_rel(path) for path in paths)
        )

    for row in entries:
        expected = {
            "entries.word_clip": canonical_word_path(row.entry_id),
            "entries.sentence_clip": canonical_sentence_path(row.entry_id),
            "entry_examples.audio_clip": canonical_sentence_path(row.entry_id),
        }
        actual = {
            "entries.word_clip": row.word_clip,
            "entries.sentence_clip": row.sentence_clip,
            "entry_examples.audio_clip": row.main_audio_clip,
        }
        for label, expected_path in expected.items():
            actual_path = normalize_stored_path(actual[label])
            if actual_path != expected_path:
                issues["noncanonical_db_paths"].append(
                    f"{row.entry_id} {label}: {actual[label]!r} -> {expected_path}"
                )
            resolved = existing_project_path(actual[label])
            if resolved is None or not resolved.exists():
                issues["stale_db_paths"].append(f"{row.entry_id} {label}: {actual[label]!r}")

        flat_word = clips_root / "words" / f"word{row.entry_id}.mp3"
        flat_sentence = clips_root / "sentences" / f"sentence{row.entry_id}.mp3"
        if not flat_word.exists():
            issues["missing_flat_files"].append(posix_rel(flat_word))
        if not flat_sentence.exists():
            issues["missing_flat_files"].append(posix_rel(flat_sentence))

    return issues


def print_report(entries: list[EntryRow], clips: ClipIndex, issues: dict[str, list[str]]) -> None:
    print(f"Entries: {len(entries)}")
    print(f"Word sources: {len(clips.word_sources)} unique, {len(clips.duplicate_words)} duplicate indexes")
    print(
        f"Sentence sources: {len(clips.sentence_sources)} unique, "
        f"{len(clips.duplicate_sentences)} duplicate indexes"
    )
    for key, values in issues.items():
        print(f"{key}: {len(values)}")
        for value in values[:20]:
            print(f"  - {value}")
        if len(values) > 20:
            print(f"  ... {len(values) - 20} more")


def copy_flat_files(entries: list[EntryRow], clips: ClipIndex, clips_root: Path) -> tuple[int, int]:
    copied = 0
    unchanged = 0
    (clips_root / "words").mkdir(parents=True, exist_ok=True)
    (clips_root / "sentences").mkdir(parents=True, exist_ok=True)

    for row in entries:
        pairs = [
            (clips.word_sources[row.entry_id], clips_root / "words" / f"word{row.entry_id}.mp3"),
            (
                clips.sentence_sources[row.entry_id],
                clips_root / "sentences" / f"sentence{row.entry_id}.mp3",
            ),
        ]
        for src, dst in pairs:
            if dst.exists() and filecmp.cmp(src, dst, shallow=False):
                unchanged += 1
                continue
            shutil.copy2(src, dst)
            copied += 1
    return copied, unchanged


def migrate_db(entries: list[EntryRow], db_path: Path) -> Path:
    backup = db_path.with_name(
        f"{db_path.name}.backup_flat_audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    shutil.copy2(db_path, backup)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            for row in entries:
                conn.execute(
                    """
                    UPDATE entries
                       SET word_clip = ?,
                           sentence_clip = ?,
                           updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
                     WHERE entry_id = ?
                    """,
                    (canonical_word_path(row.entry_id), canonical_sentence_path(row.entry_id), row.entry_id),
                )
                conn.execute(
                    """
                    UPDATE entry_examples
                       SET audio_clip = ?
                     WHERE entry_id = ?
                       AND position = 0
                    """,
                    (canonical_sentence_path(row.entry_id), row.entry_id),
                )
                conn.execute(
                    """
                    INSERT INTO entry_examples(entry_id, position, text, audio_clip)
                    SELECT entry_id, 0, COALESCE(sentence, ''), ?
                      FROM entries
                     WHERE entry_id = ?
                       AND NOT EXISTS (
                         SELECT 1
                           FROM entry_examples
                          WHERE entry_id = ?
                            AND position = 0
                       )
                    """,
                    (canonical_sentence_path(row.entry_id), row.entry_id, row.entry_id),
                )
    finally:
        conn.close()
    return backup


def fail_if_blocked(issues: dict[str, list[str]]) -> None:
    blockers = [
        "missing_word_sources",
        "missing_sentence_sources",
        "duplicate_word_sources",
        "duplicate_sentence_sources",
    ]
    blocked = {key: issues[key] for key in blockers if issues[key]}
    if blocked:
        raise SystemExit("Cannot apply while source clips are missing or duplicated.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="output/n2vocab.sqlite", help="SQLite DB path from repo root")
    parser.add_argument("--clips", default="clips", help="Clip root from repo root")
    parser.add_argument("--apply", action="store_true", help="Copy flat word/sentence files")
    parser.add_argument("--migrate-db", action="store_true", help="Update DB paths after copying flat files")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = (ROOT / args.db).resolve()
    clips_root = (ROOT / args.clips).resolve()
    entries = load_entries(db_path)
    clips = collect_clips(clips_root)
    issues = audit(entries, clips, clips_root)
    print_report(entries, clips, issues)

    if args.apply or args.migrate_db:
        fail_if_blocked(issues)

    if args.apply:
        copied, unchanged = copy_flat_files(entries, clips, clips_root)
        print(f"Flat copy complete: copied={copied}, unchanged={unchanged}")

    if args.migrate_db:
        if not args.apply:
            refreshed = audit(entries, clips, clips_root)
            missing_flat = refreshed["missing_flat_files"]
            if missing_flat:
                raise SystemExit("Cannot migrate DB until flat files exist. Run with --apply first.")
        backup = migrate_db(entries, db_path)
        print(f"DB migrated. Backup: {backup}")


if __name__ == "__main__":
    main()
