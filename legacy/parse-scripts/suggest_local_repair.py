#!/usr/bin/env python3
"""Suggest local audio repair assignments from silence-bounded pieces.

This script is meant to formalize the manual repair loop we used on Unit 3
track 19:

1. Detect stable speech pieces from silence boundaries.
2. Re-transcribe each piece with the chosen ASR backend.
3. Compare each piece span against the expected word and sentence content.
4. Search for the best sequential reassignment across a local entry window.

It does not edit any mapping or clip files on disk. Instead it produces a
reviewable suggestion artifact so a human can inspect the proposed piece ->
word/sentence assignment before applying it.

The design intentionally treats:

- silence pieces as timing truth
- ASR as identity evidence
- entry order as structural truth

That combination is much safer than trusting raw Whisper timestamps for repair.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import tempfile
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from align import (
    ROOT,
    cut_clip,
    detect_silence_boundaries,
    enumerate_speech_pieces,
    load_backend,
    transcribe_full_track,
)
from audit_review_candidates import phonetic_hiragana, ratio_score, similarity, normalize_text


@dataclass
class PieceTranscript:
    """One silence-bounded speech piece plus its isolated transcription."""

    ordinal: int
    piece_id: int
    start: float
    end: float
    text: str
    hira: str


@dataclass
class SpanCandidate:
    """Candidate assignment for either a word clip or a sentence clip.

    Each candidate spans one or more contiguous pieces. We keep both the raw
    similarity terms and the final score so the human reviewer can understand
    why a span ranked well or poorly.
    """

    entry_index: int
    kind: str
    start_ordinal: int
    end_ordinal: int
    start_piece_id: int
    end_piece_id: int
    start_time: float
    end_time: float
    piece_ids: list[int]
    transcript_text: str
    transcript_hira: str
    expected_text: str
    expected_options: list[str]
    phonetic_similarity: float
    length_score: float
    final_score: float
    notes: list[str]


@dataclass
class EntryAssignment:
    """Chosen word + sentence candidate for one entry."""

    index: int
    headword: str
    reading: str
    expected_sentence: str
    word: SpanCandidate
    sentence: SpanCandidate


@dataclass
class CurrentReviewState:
    """Snapshot of the currently saved mapping for one entry.

    The suggester is intentionally read-only, so a human reviewer needs a
    side-by-side view:

    - what the repo currently says
    - what the suggester recommends instead

    This structure keeps that comparison explicit in the output JSON and
    Markdown review note.
    """

    index: int
    note: str
    word_start: float | None
    word_end: float | None
    sentence_start: float | None
    sentence_end: float | None
    word_piece_ids: list[int]
    sentence_piece_ids: list[int]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Suggest local repair assignments from silence-bounded pieces."
    )
    parser.add_argument("--review-json", type=Path, required=True)
    parser.add_argument("--entries-json", type=Path, required=True)
    parser.add_argument("--track-name", type=str, required=True)
    parser.add_argument("--start-index", type=int, required=True)
    parser.add_argument("--end-index", type=int, required=True)
    parser.add_argument("--backend", choices=["openai", "whisper_cpp"], default="whisper_cpp")
    parser.add_argument("--model", type=str, default="base", help="OpenAI Whisper model name")
    parser.add_argument("--device", type=str, default="cpu", help="OpenAI Whisper device")
    parser.add_argument("--wcpp-binary", type=Path, default=None)
    parser.add_argument("--wcpp-model", type=Path, default=None)
    parser.add_argument("--silence-noise", type=str, default="-32dB")
    parser.add_argument("--silence-duration", type=float, default=0.25)
    parser.add_argument(
        "--piece-pad",
        type=int,
        default=1,
        help="How many silence pieces to include before and after the current review window.",
    )
    parser.add_argument(
        "--max-word-pieces",
        type=int,
        default=2,
        help="Maximum contiguous pieces to consider for one word candidate.",
    )
    parser.add_argument(
        "--max-sentence-pieces",
        type=int,
        default=5,
        help="Maximum contiguous pieces to consider for one sentence candidate.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=8,
        help="How many top-ranked word/sentence candidates per entry to keep for the global search.",
    )
    parser.add_argument("--cache-json", type=Path, default=None)
    parser.add_argument("--pieces-json", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    return parser


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def backend_cache_label(args: argparse.Namespace, backend: dict[str, Any]) -> str:
    if backend["kind"] == "openai":
        return f"openai_{args.model}"
    model_name = Path(backend["model_bin"]).stem.replace("ggml-", "")
    return f"whisper_cpp_{model_name}"


def load_cache(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    return {str(k): str(v) for k, v in json.loads(path.read_text(encoding="utf-8")).items()}


def save_cache(path: Path | None, cache: dict[str, str]) -> None:
    if path is None:
        return
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def canonical_expected_sentence(text: str) -> str:
    """Drop wrappers that are usually not part of the spoken audio."""
    cleaned = text.strip()
    cleaned = re.sub(r"^\s*[\(（][^()（）]{1,20}[\)）]\s*", "", cleaned)
    if len(cleaned) >= 2 and cleaned[0] in "「『\"" and cleaned[-1] in "」』\"":
        cleaned = cleaned[1:-1].strip()
    return cleaned


def expected_sentence_candidates(text: str) -> list[str]:
    """Split a book sentence field into spoken sentence candidates.

    Many entries contain numbered examples or bullet-separated usage lines.
    During repair we want to compare a local sentence piece only against the
    spoken sentence it is most likely to represent, not against the entire raw
    field.
    """
    cleaned = canonical_expected_sentence(text or "")
    if not cleaned:
        return []

    cleaned = re.sub(r"^\s*[\[【][^\]】]{1,20}[\]】]\s*", "", cleaned)
    cleaned = re.sub(r"[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]", " ", cleaned)
    parts = re.split(r"\s*・\s*", cleaned)

    candidates: list[str] = []
    seen: set[str] = set()
    for part in parts:
        candidate = canonical_expected_sentence(part).strip(" ・")
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        candidates.append(candidate)
    return candidates


@lru_cache(maxsize=None)
def hira(text: str) -> str:
    return phonetic_hiragana(text)


def current_track_rows(
    review_rows: list[dict[str, Any]],
    track_name: str,
    start_index: int,
    end_index: int,
) -> list[dict[str, Any]]:
    rows = [
        row
        for row in review_rows
        if row.get("track_name") == track_name and start_index <= row["index"] <= end_index
    ]
    rows.sort(key=lambda item: item["index"])
    if not rows:
        raise SystemExit(
            f"No review rows found for track {track_name!r} and indexes {start_index}-{end_index}."
        )
    return rows


def current_entry_rows(
    entries_rows: list[dict[str, Any]],
    start_index: int,
    end_index: int,
) -> list[dict[str, Any]]:
    rows = [row for row in entries_rows if start_index <= row["index"] <= end_index]
    rows.sort(key=lambda item: item["index"])
    if not rows:
        raise SystemExit(f"No entry rows found for indexes {start_index}-{end_index}.")
    return rows


def local_time_window(rows: list[dict[str, Any]]) -> tuple[float, float]:
    starts: list[float] = []
    ends: list[float] = []
    for row in rows:
        for key in ("word_start", "sentence_start"):
            value = row.get(key)
            if value is not None:
                starts.append(float(value))
        for key in ("word_end", "sentence_end"):
            value = row.get(key)
            if value is not None:
                ends.append(float(value))
    if not starts or not ends:
        raise SystemExit("The selected review rows do not have usable timing spans.")
    return min(starts), max(ends)


def overlapping_piece_ordinals(
    pieces: list[dict[str, Any]],
    start_time: float,
    end_time: float,
) -> tuple[int, int]:
    overlaps = [
        idx
        for idx, piece in enumerate(pieces)
        if not (piece["end"] <= start_time or piece["start"] >= end_time)
    ]
    if not overlaps:
        raise SystemExit("No silence pieces overlap the current review time window.")
    return overlaps[0], overlaps[-1]


def piece_cache_key(
    track_path: Path,
    piece_id: int,
    start: float,
    end: float,
    cache_label: str,
    silence_noise: str,
    silence_duration: float,
) -> str:
    rel = str(track_path.relative_to(ROOT)).replace("\\", "/")
    return (
        f"{cache_label}:{rel}:piece:{piece_id}:{start:.3f}:{end:.3f}:"
        f"{silence_noise}:{silence_duration:.3f}"
    )


def transcribe_piece(
    track_path: Path,
    piece: dict[str, Any],
    backend: dict[str, Any],
    cache: dict[str, str],
    cache_label: str,
    silence_noise: str,
    silence_duration: float,
    temp_dir: Path,
) -> str:
    key = piece_cache_key(
        track_path=track_path,
        piece_id=piece["piece_id"],
        start=piece["start"],
        end=piece["end"],
        cache_label=cache_label,
        silence_noise=silence_noise,
        silence_duration=silence_duration,
    )
    cached = cache.get(key)
    if cached is not None:
        return cached

    clip_path = temp_dir / f"piece_{piece['piece_id']}.mp3"
    cut_clip(track_path, clip_path, piece["start"], piece["end"])
    segments = transcribe_full_track(clip_path, backend=backend)
    text = "".join(segment.get("text", "") for segment in segments).strip()
    cache[key] = text
    return text


def join_piece_texts(pieces: list[PieceTranscript], start_ordinal: int, end_ordinal: int) -> str:
    return "".join(piece.text for piece in pieces[start_ordinal : end_ordinal + 1]).strip()


def overlapping_piece_ids_for_span(
    pieces: list[PieceTranscript],
    start_time: float | None,
    end_time: float | None,
) -> list[int]:
    """Map an existing time span back onto the local silence pieces.

    We use overlap rather than exact equality because older review JSON may
    contain merged or stale spans that do not line up with today's silence-piece
    boundaries. Overlap is enough to show the reviewer which local pieces the
    current mapping is effectively consuming.
    """
    if start_time is None or end_time is None:
        return []
    return [
        piece.piece_id
        for piece in pieces
        if not (piece.end <= start_time or piece.start >= end_time)
    ]


def current_review_state(row: dict[str, Any], pieces: list[PieceTranscript]) -> CurrentReviewState:
    return CurrentReviewState(
        index=row["index"],
        note=row.get("note", ""),
        word_start=row.get("word_start"),
        word_end=row.get("word_end"),
        sentence_start=row.get("sentence_start"),
        sentence_end=row.get("sentence_end"),
        word_piece_ids=overlapping_piece_ids_for_span(pieces, row.get("word_start"), row.get("word_end")),
        sentence_piece_ids=overlapping_piece_ids_for_span(pieces, row.get("sentence_start"), row.get("sentence_end")),
    )


def same_piece_assignment(candidate: SpanCandidate, piece_ids: list[int]) -> bool:
    return candidate.piece_ids == piece_ids


def candidate_rank(candidates: list[SpanCandidate], piece_ids: list[int]) -> int | None:
    for idx, candidate in enumerate(candidates, start=1):
        if same_piece_assignment(candidate, piece_ids):
            return idx
    return None


def top_alternatives(
    candidates: list[SpanCandidate],
    chosen_piece_ids: list[int],
    limit: int = 2,
) -> list[SpanCandidate]:
    """Return the best non-chosen candidates for human comparison."""
    alternatives: list[SpanCandidate] = []
    for candidate in candidates:
        if same_piece_assignment(candidate, chosen_piece_ids):
            continue
        alternatives.append(candidate)
        if len(alternatives) >= limit:
            break
    return alternatives


def expected_word_text(entry: dict[str, Any]) -> str:
    return (entry.get("reading") or entry.get("headword") or "").strip()


def best_sentence_match(entry: dict[str, Any], transcript_text: str) -> tuple[str, list[str], float, float]:
    options = expected_sentence_candidates(entry.get("sentence") or "")
    if not options:
        return "", [], 0.0, 0.0

    transcript_hira = hira(transcript_text)
    best_option = options[0]
    best_similarity = similarity(transcript_hira, hira(best_option))
    best_length = ratio_score(hira(best_option), transcript_hira)

    for option in options[1:]:
        option_hira = hira(option)
        option_similarity = similarity(transcript_hira, option_hira)
        option_length = ratio_score(option_hira, transcript_hira)
        if (option_similarity, option_length) > (best_similarity, best_length):
            best_option = option
            best_similarity = option_similarity
            best_length = option_length

    return best_option, options, best_similarity, best_length


def score_word_candidate(
    entry: dict[str, Any],
    transcript_text: str,
    piece_count: int,
) -> tuple[str, float, float, list[str], float]:
    expected = expected_word_text(entry)
    expected_hira = hira(expected)
    transcript_hira = hira(transcript_text)
    phonetic_score = similarity(transcript_hira, expected_hira)
    length_score = ratio_score(expected_hira, transcript_hira)
    notes: list[str] = []

    # Word clips should be compact. Longer spans sometimes still contain the
    # headword, but they are bad word candidates because they swallow sentence
    # material and shift everything that follows.
    final_score = phonetic_score * 0.75 + length_score * 0.25
    if piece_count > 1:
        final_score -= 0.08 * (piece_count - 1)
        notes.append(f"word_span_penalty_{piece_count}_pieces")

    sentence_option, _, sentence_similarity, _ = best_sentence_match(entry, transcript_text)
    if sentence_option and sentence_similarity >= phonetic_score + 0.10:
        final_score -= 0.20
        notes.append("word_candidate_looks_more_like_sentence")

    if normalize_text(transcript_text) and len(normalize_text(transcript_text)) >= max(6, 2 * len(normalize_text(expected))):
        final_score -= 0.20
        notes.append("word_candidate_too_long")

    return expected, phonetic_score, length_score, notes + [f"matched_word={expected}"], max(0.0, min(1.0, final_score))


def score_sentence_candidate(entry: dict[str, Any], transcript_text: str, piece_count: int) -> tuple[str, list[str], float, float, list[str], float]:
    expected, options, phonetic_score, length_score = best_sentence_match(entry, transcript_text)
    notes: list[str] = []

    # Sentence spans are allowed to be longer than word spans, but we still want
    # to push the search away from overly short fragments or accidental word-only
    # spans. The length score helps suppress strong prefix-only false positives.
    final_score = phonetic_score * 0.85 + length_score * 0.15
    if piece_count == 1 and len(normalize_text(transcript_text)) <= 4:
        final_score -= 0.10
        notes.append("sentence_candidate_is_very_short")

    expected_word = expected_word_text(entry)
    word_similarity = similarity(hira(transcript_text), hira(expected_word))
    if expected_word and word_similarity >= phonetic_score + 0.10:
        final_score -= 0.20
        notes.append("sentence_candidate_looks_more_like_word")

    return expected, options, phonetic_score, length_score, notes + [f"matched_sentence={expected}"], max(0.0, min(1.0, final_score))


def build_candidates_for_entry(
    entry: dict[str, Any],
    pieces: list[PieceTranscript],
    max_word_pieces: int,
    max_sentence_pieces: int,
    top_k: int,
) -> tuple[list[SpanCandidate], list[SpanCandidate]]:
    word_candidates: list[SpanCandidate] = []
    sentence_candidates: list[SpanCandidate] = []

    for start_ordinal in range(len(pieces)):
        max_word_end = min(len(pieces) - 1, start_ordinal + max_word_pieces - 1)
        max_sentence_end = min(len(pieces) - 1, start_ordinal + max_sentence_pieces - 1)

        for end_ordinal in range(start_ordinal, max_word_end + 1):
            transcript_text = join_piece_texts(pieces, start_ordinal, end_ordinal)
            if not transcript_text:
                continue
            expected, phonetic_score, length_score, notes, final_score = score_word_candidate(
                entry,
                transcript_text,
                piece_count=end_ordinal - start_ordinal + 1,
            )
            word_candidates.append(
                SpanCandidate(
                    entry_index=entry["index"],
                    kind="word",
                    start_ordinal=start_ordinal,
                    end_ordinal=end_ordinal,
                    start_piece_id=pieces[start_ordinal].piece_id,
                    end_piece_id=pieces[end_ordinal].piece_id,
                    start_time=pieces[start_ordinal].start,
                    end_time=pieces[end_ordinal].end,
                    piece_ids=[piece.piece_id for piece in pieces[start_ordinal : end_ordinal + 1]],
                    transcript_text=transcript_text,
                    transcript_hira=hira(transcript_text),
                    expected_text=expected,
                    expected_options=[expected],
                    phonetic_similarity=round(phonetic_score, 3),
                    length_score=round(length_score, 3),
                    final_score=round(final_score, 3),
                    notes=notes,
                )
            )

        for end_ordinal in range(start_ordinal, max_sentence_end + 1):
            transcript_text = join_piece_texts(pieces, start_ordinal, end_ordinal)
            if not transcript_text:
                continue
            expected, options, phonetic_score, length_score, notes, final_score = score_sentence_candidate(
                entry,
                transcript_text,
                piece_count=end_ordinal - start_ordinal + 1,
            )
            sentence_candidates.append(
                SpanCandidate(
                    entry_index=entry["index"],
                    kind="sentence",
                    start_ordinal=start_ordinal,
                    end_ordinal=end_ordinal,
                    start_piece_id=pieces[start_ordinal].piece_id,
                    end_piece_id=pieces[end_ordinal].piece_id,
                    start_time=pieces[start_ordinal].start,
                    end_time=pieces[end_ordinal].end,
                    piece_ids=[piece.piece_id for piece in pieces[start_ordinal : end_ordinal + 1]],
                    transcript_text=transcript_text,
                    transcript_hira=hira(transcript_text),
                    expected_text=expected,
                    expected_options=options,
                    phonetic_similarity=round(phonetic_score, 3),
                    length_score=round(length_score, 3),
                    final_score=round(final_score, 3),
                    notes=notes,
                )
            )

    word_candidates.sort(
        key=lambda item: (item.final_score, item.phonetic_similarity, -len(item.piece_ids)),
        reverse=True,
    )
    sentence_candidates.sort(
        key=lambda item: (item.final_score, item.phonetic_similarity, -len(item.piece_ids)),
        reverse=True,
    )
    return word_candidates[:top_k], sentence_candidates[:top_k]


def select_best_assignment(
    entries: list[dict[str, Any]],
    word_candidates: dict[int, list[SpanCandidate]],
    sentence_candidates: dict[int, list[SpanCandidate]],
) -> tuple[float, list[EntryAssignment]]:
    """Search the best monotonic piece assignment across the local run.

    This is the core repair idea translated into code:

    - each entry must consume one word span and one later sentence span
    - later entries must start after earlier entries end
    - the best assignment is the one with the highest total local evidence

    The recursion is small because the local window is intentionally narrow and
    each entry only keeps its top-k candidates.
    """

    @lru_cache(maxsize=None)
    def solve(entry_pos: int, next_ordinal: int) -> tuple[float, tuple[tuple[int, int], ...]]:
        if entry_pos >= len(entries):
            return 0.0, ()

        entry = entries[entry_pos]
        best_score = -math.inf
        best_plan: tuple[tuple[int, int], ...] = ()

        for word_idx, word in enumerate(word_candidates[entry["index"]]):
            if word.start_ordinal < next_ordinal:
                continue
            if word.final_score <= 0.0:
                continue

            # Small gap penalty keeps the search from skipping a better earlier
            # piece without a compelling scoring reason.
            gap_penalty = 0.02 * max(0, word.start_ordinal - next_ordinal)

            for sentence_idx, sentence in enumerate(sentence_candidates[entry["index"]]):
                if sentence.start_ordinal <= word.end_ordinal:
                    continue
                if sentence.final_score <= 0.0:
                    continue

                tail_score, tail_plan = solve(entry_pos + 1, sentence.end_ordinal + 1)
                current_score = word.final_score + sentence.final_score - gap_penalty + tail_score

                if current_score > best_score:
                    best_score = current_score
                    best_plan = ((word_idx, sentence_idx),) + tail_plan

        return best_score, best_plan

    total_score, plan = solve(0, 0)
    if not plan:
        raise SystemExit("The repair suggester could not find any sequential assignment.")

    assignments: list[EntryAssignment] = []
    for entry, (word_idx, sentence_idx) in zip(entries, plan, strict=True):
        assignments.append(
            EntryAssignment(
                index=entry["index"],
                headword=entry.get("headword", ""),
                reading=entry.get("reading", ""),
                expected_sentence=(expected_sentence_candidates(entry.get("sentence") or "") or [""])[0],
                word=word_candidates[entry["index"]][word_idx],
                sentence=sentence_candidates[entry["index"]][sentence_idx],
            )
        )
    return round(total_score, 3), assignments


def markdown_piece_line(piece: PieceTranscript) -> str:
    return (
        f"- piece {piece.piece_id}: `{piece.start:.3f}-{piece.end:.3f}` "
        f"`{piece.text}`"
    )


def markdown_candidate_line(label: str, candidate: SpanCandidate) -> str:
    return (
        f"- {label}: pieces `{candidate.start_piece_id}-{candidate.end_piece_id}` "
        f"| span `{candidate.start_time:.3f}-{candidate.end_time:.3f}` "
        f"| score `{candidate.final_score}` "
        f"| text `{candidate.transcript_text}`"
    )


def markdown_current_line(label: str, piece_ids: list[int], start_time: float | None, end_time: float | None) -> str:
    span_text = (
        f"`{start_time:.3f}-{end_time:.3f}`"
        if start_time is not None and end_time is not None
        else "`missing`"
    )
    pieces_text = ",".join(str(piece_id) for piece_id in piece_ids) if piece_ids else "none"
    return f"- current {label}: pieces `{pieces_text}` | span {span_text}"


def main() -> None:
    args = build_parser().parse_args()
    review_rows = json.loads(args.review_json.read_text(encoding="utf-8"))
    entries_rows = json.loads(args.entries_json.read_text(encoding="utf-8"))

    target_review_rows = current_track_rows(
        review_rows=review_rows,
        track_name=args.track_name,
        start_index=args.start_index,
        end_index=args.end_index,
    )
    target_entries = current_entry_rows(
        entries_rows=entries_rows,
        start_index=args.start_index,
        end_index=args.end_index,
    )

    track_path = ROOT / target_review_rows[0]["track_path"].replace("\\", "/")
    backend = load_backend(
        args.backend,
        model_name=args.model,
        device=args.device,
        wcpp_binary=args.wcpp_binary,
        wcpp_model=args.wcpp_model,
    )
    cache_label = backend_cache_label(args, backend)
    cache = load_cache(args.cache_json)

    boundaries, duration = detect_silence_boundaries(
        track_path,
        noise=args.silence_noise,
        min_dur=args.silence_duration,
    )
    all_pieces = enumerate_speech_pieces(boundaries, duration)
    win_start, win_end = local_time_window(target_review_rows)
    overlap_start, overlap_end = overlapping_piece_ordinals(all_pieces, win_start, win_end)
    window_start = max(0, overlap_start - args.piece_pad)
    window_end = min(len(all_pieces) - 1, overlap_end + args.piece_pad)
    selected_piece_defs = all_pieces[window_start : window_end + 1]

    with tempfile.TemporaryDirectory(dir=ROOT / "output") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        selected_pieces: list[PieceTranscript] = []
        for ordinal, piece in enumerate(selected_piece_defs):
            text = transcribe_piece(
                track_path=track_path,
                piece=piece,
                backend=backend,
                cache=cache,
                cache_label=cache_label,
                silence_noise=args.silence_noise,
                silence_duration=args.silence_duration,
                temp_dir=temp_dir,
            )
            selected_pieces.append(
                PieceTranscript(
                    ordinal=ordinal,
                    piece_id=piece["piece_id"],
                    start=piece["start"],
                    end=piece["end"],
                    text=text,
                    hira=hira(text),
                )
            )

    save_cache(args.cache_json, cache)

    review_by_index = {row["index"]: row for row in target_review_rows}
    per_entry_word_candidates: dict[int, list[SpanCandidate]] = {}
    per_entry_sentence_candidates: dict[int, list[SpanCandidate]] = {}
    for entry in target_entries:
        word_candidates, sentence_candidates = build_candidates_for_entry(
            entry=entry,
            pieces=selected_pieces,
            max_word_pieces=args.max_word_pieces,
            max_sentence_pieces=args.max_sentence_pieces,
            top_k=args.top_k,
        )
        per_entry_word_candidates[entry["index"]] = word_candidates
        per_entry_sentence_candidates[entry["index"]] = sentence_candidates

    total_score, assignments = select_best_assignment(
        entries=target_entries,
        word_candidates=per_entry_word_candidates,
        sentence_candidates=per_entry_sentence_candidates,
    )

    pieces_payload = {
        "track_name": args.track_name,
        "track_path": str(track_path.relative_to(ROOT)).replace("/", "\\"),
        "silence_noise": args.silence_noise,
        "silence_duration": args.silence_duration,
        "window_time": {"start": round(win_start, 3), "end": round(win_end, 3)},
        "window_piece_ids": [piece.piece_id for piece in selected_pieces],
        "pieces": [asdict(piece) for piece in selected_pieces],
    }
    args.pieces_json.write_text(
        json.dumps(pieces_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    output_payload = {
        "track_name": args.track_name,
        "track_path": str(track_path.relative_to(ROOT)).replace("/", "\\"),
        "backend": cache_label,
        "score_total": total_score,
        "settings": {
            "silence_noise": args.silence_noise,
            "silence_duration": args.silence_duration,
            "piece_pad": args.piece_pad,
            "max_word_pieces": args.max_word_pieces,
            "max_sentence_pieces": args.max_sentence_pieces,
            "top_k": args.top_k,
        },
        "indexes": [entry["index"] for entry in target_entries],
        "assignments": [
            {
                "index": assignment.index,
                "headword": assignment.headword,
                "reading": assignment.reading,
                "expected_sentence": assignment.expected_sentence,
                "current_review": asdict(current_review_state(review_by_index[assignment.index], selected_pieces)),
                "word": asdict(assignment.word),
                "sentence": asdict(assignment.sentence),
                "current_word_rank": candidate_rank(
                    per_entry_word_candidates[assignment.index],
                    current_review_state(review_by_index[assignment.index], selected_pieces).word_piece_ids,
                ),
                "current_sentence_rank": candidate_rank(
                    per_entry_sentence_candidates[assignment.index],
                    current_review_state(review_by_index[assignment.index], selected_pieces).sentence_piece_ids,
                ),
                "top_word_candidates": [asdict(candidate) for candidate in per_entry_word_candidates[assignment.index]],
                "top_sentence_candidates": [
                    asdict(candidate) for candidate in per_entry_sentence_candidates[assignment.index]
                ],
                "word_alternatives": [
                    asdict(candidate)
                    for candidate in top_alternatives(
                        per_entry_word_candidates[assignment.index],
                        assignment.word.piece_ids,
                    )
                ],
                "sentence_alternatives": [
                    asdict(candidate)
                    for candidate in top_alternatives(
                        per_entry_sentence_candidates[assignment.index],
                        assignment.sentence.piece_ids,
                    )
                ],
            }
            for assignment in assignments
        ],
    }
    args.output_json.write_text(
        json.dumps(output_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        f"# Local repair suggestion: {args.track_name}",
        "",
        f"- Review JSON: `{display_path(args.review_json)}`",
        f"- Entries JSON: `{display_path(args.entries_json)}`",
        f"- Backend: `{cache_label}`",
        f"- Index window: `{args.start_index}-{args.end_index}`",
        f"- Piece window: `{selected_pieces[0].piece_id}-{selected_pieces[-1].piece_id}`",
        f"- Silence settings: noise `{args.silence_noise}` | duration `{args.silence_duration}`",
        f"- Total assignment score: `{total_score}`",
        "",
        "## Piece transcripts",
        "",
    ]
    lines.extend(markdown_piece_line(piece) for piece in selected_pieces)
    lines.extend(["", "## Suggested assignments", ""])

    for assignment in assignments:
        current = current_review_state(review_by_index[assignment.index], selected_pieces)
        word_alts = top_alternatives(per_entry_word_candidates[assignment.index], assignment.word.piece_ids)
        sentence_alts = top_alternatives(
            per_entry_sentence_candidates[assignment.index],
            assignment.sentence.piece_ids,
        )
        lines.extend(
            [
                f"### {assignment.index} {assignment.headword}",
                "",
                markdown_current_line("word", current.word_piece_ids, current.word_start, current.word_end),
                markdown_current_line(
                    "sentence",
                    current.sentence_piece_ids,
                    current.sentence_start,
                    current.sentence_end,
                ),
                f"- current note: {current.note or 'none'}",
                "",
                markdown_candidate_line("word", assignment.word),
                markdown_candidate_line("sentence", assignment.sentence),
                "",
                "Top alternatives:",
                "",
            ]
        )
        if word_alts:
            for idx, candidate in enumerate(word_alts, start=1):
                lines.append(markdown_candidate_line(f"word alt {idx}", candidate))
        else:
            lines.append("- word alt: none")
        if sentence_alts:
            for idx, candidate in enumerate(sentence_alts, start=1):
                lines.append(markdown_candidate_line(f"sentence alt {idx}", candidate))
        else:
            lines.append("- sentence alt: none")
        lines.append("")

    args.output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "track": args.track_name,
                "indexes": [entry["index"] for entry in target_entries],
                "piece_window": [selected_pieces[0].piece_id, selected_pieces[-1].piece_id],
                "score_total": total_score,
                "pieces_json": display_path(args.pieces_json),
                "output_json": display_path(args.output_json),
                "output_md": display_path(args.output_md),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
