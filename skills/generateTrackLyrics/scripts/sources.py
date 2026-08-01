"""Load authoritative text, clip paths, and source-track mappings."""

from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

from model import ClipRequest, EntryRequest


N3_RANGE_RE = re.compile(r"_id(?P<start>\d+)-(?P<end>\d+)", re.IGNORECASE)


def display_word(headword: str, reading: str) -> str:
    headword = (headword or reading).strip()
    reading = (reading or "").strip()
    if reading and reading != headword:
        return f"{headword}【{reading}】"
    return headword


def load_n1_manifest(n1_root: Path) -> tuple[list[dict], dict]:
    path = n1_root / "data" / "processed" / "audio_clips" / "clip_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("status") != "accepted":
        raise ValueError(f"N1 clip manifest is not accepted: {path}")
    return data["clips"], data


def open_live_db(repo_root: Path) -> sqlite3.Connection:
    path = (repo_root / "wordService" / "data" / "n2vocab.sqlite").resolve()
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def load_n2_entries(repo_root: Path) -> list[EntryRequest]:
    connection = open_live_db(repo_root)
    rows = connection.execute(
        """
        SELECT source_index, unit_number, kanji, reading, sentence,
               word_clip, sentence_clip
        FROM entries
        WHERE book_code = 'N2'
        ORDER BY source_index
        """
    ).fetchall()
    connection.close()

    audio_root = repo_root / "audio"

    def source_directory(row: sqlite3.Row) -> Path:
        """Resolve the two review chapters that share a numeric DB unit.

        The live database intentionally numbers まとめ1 as unit 4 and まとめ2
        as unit 7, while their CD folders are named Unit4.5 and Unit7.5.
        Source index is the stable ordering contract that distinguishes them.
        """
        source_index = int(row["source_index"])
        unit = int(row["unit_number"])
        label = "4.5" if 371 <= source_index <= 460 else "7.5" if 656 <= source_index <= 680 else str(unit)
        pattern = re.compile(rf"^Unit{re.escape(label)}(?:\s|$)")
        directories = [path for path in audio_root.iterdir() if path.is_dir() and pattern.match(path.name)]
        if len(directories) != 1:
            raise ValueError(f"Expected one N2 source directory for entry {source_index}, found {directories}")
        return directories[0]

    tracks_by_directory: dict[Path, list[str]] = {}

    entries: list[EntryRequest] = []
    for row in rows:
        entry_id = int(row["source_index"])
        unit = int(row["unit_number"])
        directory = source_directory(row)
        if directory not in tracks_by_directory:
            tracks_by_directory[directory] = [str(path.resolve()) for path in sorted(directory.glob("*.mp3"))]
        word_clip = _existing(repo_root / row["word_clip"])
        sentence_clip = _existing(repo_root / row["sentence_clip"])
        entries.append(
            EntryRequest(
                entry_id=entry_id,
                unit_number=unit,
                headword=row["kanji"] or row["reading"],
                reading=row["reading"] or "",
                word=ClipRequest(entry_id, "word", display_word(row["kanji"], row["reading"]), word_clip),
                sentences=[ClipRequest(entry_id, "sentence", row["sentence"], sentence_clip, 0)],
                source_candidates=tracks_by_directory[directory],
            )
        )
    return entries


def load_n3_entries(repo_root: Path, n3_root: Path) -> list[EntryRequest]:
    connection = open_live_db(repo_root)
    word_rows = connection.execute(
        """
        SELECT entry_id, source_index, unit_number, kanji, reading, word_clip
        FROM entries
        WHERE book_code = 'N3'
        ORDER BY source_index
        """
    ).fetchall()
    sentence_rows = connection.execute(
        """
        SELECT e.source_index, x.position, x.text, x.audio_clip
        FROM entry_examples x
        JOIN entries e ON e.entry_id = x.entry_id
        WHERE e.book_code = 'N3'
          AND x.audio_clip LIKE 'clips/n3/sentences/%'
          AND x.position = 0
        ORDER BY e.source_index, x.position
        """
    ).fetchall()
    connection.close()

    sentences: dict[int, list[ClipRequest]] = defaultdict(list)
    for row in sentence_rows:
        clip = _existing(repo_root / row["audio_clip"])
        sentences[int(row["source_index"])].append(
            ClipRequest(
                int(row["source_index"]),
                "sentence",
                row["text"],
                clip,
                int(row["position"]),
            )
        )

    # The N3 deck also has later study audio for additional examples. Those
    # files are useful on cards but are not excerpts from the original CD
    # tracks. Position 0 is the book/CD main example and is the only sentence
    # contract used for track lyrics.

    ranged_tracks: list[tuple[int, int, str]] = []
    for path in sorted((n3_root / "audio" / "tracks").rglob("*.mp3")):
        match = N3_RANGE_RE.search(path.stem)
        if match:
            ranged_tracks.append((int(match.group("start")), int(match.group("end")), str(path.resolve())))

    entries: list[EntryRequest] = []
    for row in word_rows:
        entry_id = int(row["source_index"])
        candidates = [path for start, end, path in ranged_tracks if start <= entry_id <= end]
        if len(candidates) != 1:
            raise ValueError(
                f"N3 entry {entry_id} must be covered by exactly one source range; found {candidates}"
            )
        raw_word_clip = row["word_clip"] or ""
        # The live DB deliberately falls back to TTS for unresolved CD words.
        # A TTS file must never be compared against or presented as CD evidence.
        word_clip = None
        if raw_word_clip.replace("\\", "/").startswith("clips/n3/words/"):
            word_clip = _existing(repo_root / raw_word_clip)
        entries.append(
            EntryRequest(
                entry_id=entry_id,
                unit_number=int(row["unit_number"]),
                headword=row["kanji"] or row["reading"],
                reading=row["reading"] or "",
                word=ClipRequest(
                    entry_id,
                    "word",
                    display_word(row["kanji"], row["reading"]),
                    word_clip,
                ),
                sentences=sentences.get(entry_id, []),
                source_candidates=candidates,
            )
        )

    # Some track filenames describe a printed page range containing IDs that
    # are intentionally absent from the canonical/live N3 dataset. The strict
    # invariant is therefore one-way: every live entry must resolve to exactly
    # one track (checked above). A filename's extra range labels must not create
    # vocabulary rows or lyrics by themselves.
    return entries


def _existing(path: Path) -> str:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return str(resolved)
