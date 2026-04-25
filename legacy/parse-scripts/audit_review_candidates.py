#!/usr/bin/env python3
"""Audit uncertain audio alignments for the N2 vocabulary dataset.

## Role in the pipeline

align_track_by_llm.py cuts clips and writes a `needs_review` flag on items
where the match confidence was low (shared region, single chunk, weak score).
This script is the second pass: it re-examines every flagged item using more
evidence than the first pass had, and tries to automatically clear the easy
false positives so the human reviewer only sees genuinely ambiguous cases.

## Design principles

1. **Index order is structural truth.**
   The book plays entries in strict index order on each track. Even when ASR
   output is noisy, the order constraint lets us reject candidates that would
   require an impossible timeline jump.

2. **Silence boundaries are timing truth.**
   ffmpeg silencedetect gives stable, reproducible boundaries tied to the actual
   waveform. These are used as candidate windows, not Whisper timestamps.

3. **ASR output is soft identity evidence only.**
   Whisper frequently mistranscribes kanji, drops particles, or merges adjacent
   words. It is used for scoring ("does this audio window sound like entry X?"),
   never for deciding where to cut.

4. **Phonetic (hiragana) comparison beats surface text.**
   Because Whisper gets the reading right more often than the exact surface form,
   all similarity scoring is done on `phonetic_hiragana()` projections.

5. **Strong trusted neighbors constrain uncertain items.**
   If the item before and after a suspect item are both trusted, the suspect
   must live in the time gap between them. The bounded-run and bounded-gap
   solvers exploit this to dramatically reduce the search space.

## Two-solver architecture

Phase 1 — bounded-run solver: when a consecutive block of uncertain items sits
  between two trusted anchors on the same track, it treats the whole block as
  a small ordered assignment problem and solves it with dynamic programming.
  This handles the common case where two or three adjacent entries were all
  flagged but are clearly sequential in the audio.

Phase 2 — per-item audit: for items that the bounded-run solver couldn't handle,
  audits each item individually using its original transcript, clip re-transcription,
  and neighbor support scores. Falls back to the bounded-gap rescue for
  `no_matching_track_content` items (entries that never got a clip at all).

## Transcription backends

Two Whisper backends are used for different purposes:
- faster_whisper (WhisperModel) — used only in `get_track_segments()` for
  whole-track coarse segmentation during the rescue pass. Produces rough segment
  timestamps fast without subprocess overhead.
- openai_whisper or whisper_cpp (TranscriptionBackend) — used for clip-level
  and window-level re-transcription throughout the scoring pass. whisper_cpp
  uses the AMD Vulkan GPU for ~10x speedup on this machine.

The script writes three main outputs:

- ``review_audit_results.json``: every originally reviewed item with new scores
- ``review_auto_approved.json``: items cleared automatically
- ``review_still_needs_human.json``: items that still look risky
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Any

import jaconv
from fugashi import Tagger
from faster_whisper import WhisperModel
import whisper as openai_whisper

ROOT = Path(__file__).resolve().parents[2]
COMBINED_JSON = ROOT / "output" / "vocabulary_combined.json"
MANIFEST_JSON = ROOT / "output" / "audio_alignment_manifest.json"
OUTPUT_DIR = ROOT / "output"
MANUAL_VERIFIED_JSON = OUTPUT_DIR / "manual_verified_indexes.json"
OPENAI_WHISPER_CACHE_JSON = OUTPUT_DIR / "openai_whisper_clip_cache.json"
DEFAULT_WHISPER_CPP_BIN = ROOT / "tools" / "whispercpp-windows" / "whisper-cli.exe"
DEFAULT_WHISPER_CPP_MODEL = ROOT / "tools" / "whispercpp-windows" / "ggml-large-v3-turbo.bin"

# We normalize away punctuation and spacing because OCR/ASR noise in this
# project is much more about wrong kanji/kana tokens than about punctuation.
PUNCT_RE = re.compile(r"[「」『』（）()［］\[\]{}<>【】・….,，、／/'!！?？:：;；\-ー~〜→⇒=＋+※\s]")
TRACK_NUM_RE = re.compile(r"^(\d+)")
tagger = Tagger()


@dataclass
class TrackSegment:
    """A coarse ASR segment from a full audio track.

    Attributes:
        index: Segment index from the ASR output.
        start: Segment start time in seconds.
        end: Segment end time in seconds.
        text: Original ASR text for the segment.
        hira: Hiragana-normalized form of ``text`` for phonetic comparison.
    """

    index: int
    start: float
    end: float
    text: str
    hira: str


@dataclass
class ClipTranscript:
    """Transcript pair for already-cut word/sentence clips.

    Attributes:
        word_text: ASR text for the isolated word clip.
        sentence_text: ASR text for the isolated sentence clip.
        word_hira: Hiragana-normalized version of ``word_text``.
        sentence_hira: Hiragana-normalized version of ``sentence_text``.
    """

    word_text: str
    sentence_text: str
    word_hira: str
    sentence_hira: str


@dataclass
class TranscriptionBackend:
    """Configuration for the active transcription engine.

    The audit code uses one abstraction so that transcription can come from
    different backends:

    - ``openai_whisper`` for the local Python package
    - ``whisper_cpp`` for the Windows Vulkan CLI

    Attributes:
        kind: Backend identifier.
        model: Python model object when using the in-process backend.
        whisper_cpp_bin: Path to ``whisper-cli`` when using ``whisper_cpp``.
        whisper_cpp_model: Path to the ggml model file for ``whisper_cpp``.
        whisper_cpp_threads: Thread count passed to ``whisper.cpp``.
    """

    kind: str
    model: Any
    whisper_cpp_bin: str | None = None
    whisper_cpp_model: str | None = None
    whisper_cpp_threads: int = 8


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line interface for the audit script.

    Returns:
        An argument parser with file-path overrides for the main inputs and
        outputs.
    """

    # The CLI is intentionally simple because this script is a second-pass audit
    # over already-generated data, not a full pipeline in itself.
    parser = argparse.ArgumentParser(
        description="Audit review candidates using transcript similarity plus index-order/track-position anchors."
    )
    parser.add_argument("--combined-json", type=Path, default=COMBINED_JSON)
    parser.add_argument("--manifest-json", type=Path, default=MANIFEST_JSON)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--manual-verified-json", type=Path, default=MANUAL_VERIFIED_JSON)
    parser.add_argument("--openai-whisper-cache-json", type=Path, default=OPENAI_WHISPER_CACHE_JSON)
    return parser


def build_transcription_backend() -> TranscriptionBackend:
    """Create the configured transcription backend.

    The backend is chosen via environment variables so the same scoring code can
    be reused with either an in-process Python model or the Windows Vulkan
    ``whisper.cpp`` CLI.

    Environment variables:
      WHISPER_TRANSCRIBE_BACKEND — "openai_whisper" (default) or "whisper_cpp"
      WHISPER_CPP_BIN            — path to whisper-cli.exe (whisper_cpp only)
      WHISPER_CPP_MODEL          — path to ggml-*.bin model (whisper_cpp only)
      WHISPER_CPP_THREADS        — thread count, default 8

    Returns:
        A populated backend descriptor that downstream helpers know how to call.
    """

    backend_kind = os.environ.get("WHISPER_TRANSCRIBE_BACKEND", "openai_whisper").strip().lower()
    if backend_kind == "whisper_cpp":
        whisper_cpp_bin = os.environ.get("WHISPER_CPP_BIN") or str(DEFAULT_WHISPER_CPP_BIN)
        whisper_cpp_model = os.environ.get("WHISPER_CPP_MODEL") or str(DEFAULT_WHISPER_CPP_MODEL)
        threads = int(os.environ.get("WHISPER_CPP_THREADS", "8"))
        return TranscriptionBackend(
            kind="whisper_cpp",
            model=None,
            whisper_cpp_bin=whisper_cpp_bin,
            whisper_cpp_model=whisper_cpp_model,
            whisper_cpp_threads=threads,
        )
    return TranscriptionBackend(
        kind="openai_whisper",
        model=openai_whisper.load_model("tiny"),
    )


def main() -> None:
    """Run the full second-pass audit workflow.

    The workflow has two stages:

    1. Solve bounded unresolved runs that sit between trusted neighbors.
    2. Audit any remaining review items individually.

    Side Effects:
        Rewrites the audit result JSON files, the manifest, the combined
        vocabulary JSON, and the derived review-only exports.
    """

    # Data flow:
    # 1. Load the combined ground-truth-like vocabulary data.
    # 2. Load the alignment manifest produced by the audio pipeline.
    # 3. Re-score only the items that still need review.
    # 4. Split them into "auto-approved" vs "still needs human".
    args = build_parser().parse_args()
    combined = json.loads(args.combined_json.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest_json.read_text(encoding="utf-8"))
    entries_by_index = {entry["index"]: entry for entry in combined}
    whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
    transcriber = build_transcription_backend()
    manual_verified_indexes = load_manual_verified_indexes(args.manual_verified_json)
    clip_cache = load_openai_whisper_cache(args.openai_whisper_cache_json)
    track_cache: dict[str, list[TrackSegment]] = {}
    silence_cache: dict[str, list[tuple[float, float]]] = {}
    combined_by_index = {entry["index"]: entry for entry in combined}
    trusted_indexes = {
        item["index"]
        for item in manifest
        if (not item.get("needs_review")) or (item["index"] in manual_verified_indexes)
    }
    original_review_indexes = [item["index"] for item in manifest if item.get("needs_review")]

    results_by_index: dict[int, dict[str, Any]] = {}
    bounded_run_results: list[dict[str, Any]] = []
    processed_run_indexes: set[int] = set()

    # Phase 1: solve whole bounded unresolved runs before we fall back to
    # per-item auditing. This is the new "mini-track" solver that turns each
    # run between trusted anchors into its own local matching problem.
    pos = 0
    while pos < len(manifest):
        item = manifest[pos]
        if item["index"] in trusted_indexes:
            pos += 1
            continue

        run = detect_bounded_unresolved_run(manifest, pos, trusted_indexes)
        if run is None:
            pos += 1
            continue

        run_indexes = [manifest[idx]["index"] for idx in run["positions"]]
        processed_run_indexes.update(run_indexes)
        run_result = solve_bounded_run(
            manifest=manifest,
            combined_by_index=combined_by_index,
            run=run,
            transcriber=transcriber,
            clip_cache=clip_cache,
            silence_cache=silence_cache,
        )
        bounded_run_results.append(run_result)

        if run_result["audit_decision"] == "auto_approved":
            for assignment in run_result["assignments"]:
                original_item = dict(item_by_index(manifest, assignment["index"]))
                promoted = promote_run_assignment(
                    manifest=manifest,
                    combined_by_index=combined_by_index,
                    assignment=assignment,
                )
                trusted_indexes.add(assignment["index"])
                results_by_index[assignment["index"]] = build_run_audit_result(
                    original_item=original_item,
                    entry=combined_by_index[assignment["index"]],
                    assignment=assignment,
                    run_result=run_result,
                )

        pos = run["end_pos"] + 1

    # Phase 2: run the existing per-item audit on everything that remains in
    # review after the bounded-run promotions above.
    for pos, item in enumerate(manifest):
        if item["index"] not in original_review_indexes:
            continue
        if item["index"] in results_by_index:
            continue
        if not item.get("needs_review"):
            continue

        entry = entries_by_index.get(item["index"], {})
        audit = audit_item(
            manifest=manifest,
            pos=pos,
            item=item,
            entry=entry,
            whisper_model=whisper_model,
            transcriber=transcriber,
            track_cache=track_cache,
            clip_cache=clip_cache,
            manual_verified_indexes=manual_verified_indexes,
            trusted_indexes=trusted_indexes,
            silence_cache=silence_cache,
        )
        results_by_index[item["index"]] = audit
        if audit["audit_decision"] == "auto_approved":
            trusted_indexes.add(item["index"])

    results = [results_by_index[index] for index in original_review_indexes if index in results_by_index]
    auto_approved = [item for item in results if item["audit_decision"] == "auto_approved"]
    still_review = [item for item in results if item["audit_decision"] != "auto_approved"]

    output_dir = args.output_dir.resolve()
    all_path = output_dir / "review_audit_results.json"
    approved_path = output_dir / "review_auto_approved.json"
    review_path = output_dir / "review_still_needs_human.json"
    bounded_run_path = output_dir / "bounded_run_solver_results.json"

    all_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    approved_path.write_text(json.dumps(auto_approved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    review_path.write_text(json.dumps(still_review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bounded_run_path.write_text(json.dumps(bounded_run_results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.openai_whisper_cache_json.write_text(json.dumps(clip_cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.manifest_json.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.combined_json.write_text(json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_review_candidates(manifest, combined, output_dir)

    print(
        json.dumps(
            {
                "review_items": len(original_review_indexes),
                "auto_approved": len(auto_approved),
                "still_needs_human": len(still_review),
                "all_results": str(all_path.relative_to(ROOT)),
                "auto_approved_path": str(approved_path.relative_to(ROOT)),
                "still_review_path": str(review_path.relative_to(ROOT)),
                "bounded_run_results_path": str(bounded_run_path.relative_to(ROOT)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def item_by_index(manifest: list[dict[str, Any]], index: int) -> dict[str, Any]:
    """Look up a manifest row by global vocabulary index.

    Args:
        manifest: Full alignment manifest.
        index: Global book index to locate.

    Returns:
        The matching manifest row.

    Raises:
        KeyError: If the index is missing from the manifest.
    """

    for item in manifest:
        if item["index"] == index:
            return item
    raise KeyError(index)


def detect_bounded_unresolved_run(
    manifest: list[dict[str, Any]],
    pos: int,
    trusted_indexes: set[int],
) -> dict[str, Any] | None:
    """Detect a run of unresolved items bracketed by trusted neighbors.

    This is the key structural observation behind the bounded-run solver. If a
    consecutive block of review items sits between two already trusted items on
    the same track, then the unresolved block must live inside that time gap.

    Args:
        manifest: Full alignment manifest in book order.
        pos: Candidate start position in ``manifest``.
        trusted_indexes: Global indexes already considered trustworthy.

    Returns:
        A run descriptor when a two-sided bounded run exists, otherwise
        ``None``.
    """

    current = manifest[pos]
    if is_trusted_anchor(current, trusted_indexes):
        return None
    if not current.get("needs_review"):
        return None
    if pos > 0 and not is_trusted_anchor(manifest[pos - 1], trusted_indexes):
        return None

    prev_pos = pos - 1
    if prev_pos < 0 or not is_trusted_anchor(manifest[prev_pos], trusted_indexes):
        return None

    end_pos = pos
    while end_pos < len(manifest) and not is_trusted_anchor(manifest[end_pos], trusted_indexes):
        if not manifest[end_pos].get("needs_review"):
            return None
        end_pos += 1
    if end_pos >= len(manifest):
        return None

    next_pos = end_pos
    prev_anchor = manifest[prev_pos]
    next_anchor = manifest[next_pos]
    if not prev_anchor.get("track_path") or prev_anchor.get("track_path") != next_anchor.get("track_path"):
        return None
    if prev_anchor.get("sentence_end") is None or next_anchor.get("word_start") is None:
        return None
    if next_anchor["word_start"] <= prev_anchor["sentence_end"]:
        return None

    return {
        "start_pos": pos,
        "end_pos": next_pos - 1,
        "positions": list(range(pos, next_pos)),
        "indexes": [manifest[idx]["index"] for idx in range(pos, next_pos)],
        "track_path": prev_anchor["track_path"],
        "track_name": prev_anchor["track_name"],
        "prev_anchor": prev_anchor,
        "next_anchor": next_anchor,
        "run_start": round(prev_anchor["sentence_end"], 4),
        "run_end": round(next_anchor["word_start"], 4),
    }


def solve_bounded_run(
    manifest: list[dict[str, Any]],
    combined_by_index: dict[int, dict[str, Any]],
    run: dict[str, Any],
    transcriber: TranscriptionBackend,
    clip_cache: dict[str, str],
    silence_cache: dict[str, list[tuple[float, float]]],
) -> dict[str, Any]:
    """Solve one bounded unresolved run as a whole ordered sequence.

    The solver treats the bounded time gap as a small local search problem.
    It enumerates silence-bounded candidate windows, scores them, and uses
    dynamic programming to find the best non-overlapping assignment for the
    entire run.

    Why dynamic programming?
    A greedy approach (assign the best window for item 1, then item 2, ...) fails
    when the best local choice for item 1 uses too many chunks and leaves item 2
    with nothing good. DP searches all valid sequential assignments and picks the
    globally optimal path. The state is (item_index, chunk_index), and the search
    is bounded in practice because runs rarely exceed 4-5 items and 15-20 chunks
    (the solver bails at 12 items or 28 chunks).

    Args:
        manifest: Full alignment manifest.
        combined_by_index: Vocabulary entries keyed by global index.
        run: Run descriptor returned by ``detect_bounded_unresolved_run``.
        transcriber: Active ASR backend.
        clip_cache: Transcript cache reused across windows.
        silence_cache: Cache of ``ffmpeg`` silence chunks by track.

    Returns:
        A debug/result dictionary describing the chosen path or failure reason.
    """

    run_entries = [combined_by_index[manifest[pos]["index"]] for pos in run["positions"]]
    track_path = run["track_path"]
    atomic_chunks = [
        (start, end)
        for start, end in get_silence_chunks(track_path, silence_cache)
        if start >= run["run_start"] - 0.05 and end <= run["run_end"] + 0.05
    ]
    debug_result = {
        "solver_type": "bounded_run_openai",
        "run_indexes": run["indexes"],
        "track_path": track_path,
        "track_name": run["track_name"],
        "run_start": run["run_start"],
        "run_end": run["run_end"],
        "anchor_prev_index": run["prev_anchor"]["index"],
        "anchor_next_index": run["next_anchor"]["index"],
        "anchor_prev_end": run["prev_anchor"]["sentence_end"],
        "anchor_next_start": run["next_anchor"]["word_start"],
        "atomic_chunks": [{"start": start, "end": end} for start, end in atomic_chunks],
        "audit_decision": "needs_human_review",
        "assignments": [],
    }
    if not atomic_chunks:
        debug_result["failure_reason"] = "no_atomic_chunks_in_run"
        return debug_result
    if len(run_entries) > 12:
        debug_result["failure_reason"] = "run_too_large_item_count"
        return debug_result
    if len(atomic_chunks) > 28:
        debug_result["failure_reason"] = "run_too_large_chunk_count"
        return debug_result

    @lru_cache(maxsize=None)
    def best_path(item_idx: int, chunk_idx: int) -> tuple[float, tuple[dict[str, Any], ...]]:
        """Return the best remaining assignment from one DP state.

        The DP state is (item_idx, chunk_idx): "starting from item_idx and
        chunk_idx, what is the highest-scoring complete assignment of all
        remaining items?"

        Base cases:
        - All items placed: small residual penalty for unused trailing chunks
          so the solver prefers filling the whole bounded region rather than
          stopping as soon as all items are placed.
        - Chunks exhausted before items: -10000 (impossible state, hard reject).

        Transitions:
        - Skip current chunk (−0.08 penalty): allows the solver to skip a
          filler noise burst or an ASR-hostile chunk without failing the whole run.
        - Assign current chunk(s) to current item via generate_run_candidates:
          tries both same-segment and split-segment shapes.

        Args:
            item_idx: Offset into the unresolved run items.
            chunk_idx: Offset into the local atomic silence chunks.

        Returns:
            A tuple of ``(score, assignments)`` for the best continuation.
        """

        if item_idx >= len(run_entries):
            # Small end penalty so the solver prefers using the bounded span
            # instead of stopping too early and leaving many chunks unused.
            return (-0.03 * (len(atomic_chunks) - chunk_idx), ())
        if chunk_idx >= len(atomic_chunks):
            return (-10_000.0, ())

        best_score = -10_000.0
        best_assignments: tuple[dict[str, Any], ...] = ()

        # Allow a small skip penalty for noise or ASR-hostile filler chunks.
        skip_score, skip_assignments = best_path(item_idx, chunk_idx + 1)
        skip_total = skip_score - 0.08
        if skip_total > best_score:
            best_score = skip_total
            best_assignments = skip_assignments

        for candidate in generate_run_candidates(
            entry=run_entries[item_idx],
            track_path=track_path,
            atomic_chunks=atomic_chunks,
            chunk_idx=chunk_idx,
            transcriber=transcriber,
            clip_cache=clip_cache,
            run=run,
        ):
            future_score, future_assignments = best_path(item_idx + 1, candidate["next_chunk_index"])
            total = candidate["weighted_audit_score"] + future_score
            if total > best_score:
                best_score = total
                best_assignments = (candidate,) + future_assignments

        return best_score, best_assignments

    best_score, assignments = best_path(0, 0)
    debug_result["best_path_score"] = round(best_score, 4)
    debug_result["assignments"] = [strip_next_chunk_index(dict(item)) for item in assignments]
    if len(assignments) != len(run_entries):
        debug_result["failure_reason"] = "incomplete_run_assignment"
        return debug_result

    # Auto-approve only when every item in the run clears all three thresholds.
    # The sentence_end threshold (0.50) is intentionally lower than the global
    # weighted_score threshold (0.72) because the end of a sentence in Japanese
    # audio is often cut short by the next silence — the final mora gets clipped.
    # Sentence_kana (0.60) is a harder requirement because kana-level similarity
    # is already lenient about kanji/kana representation differences.
    weak_indexes = [
        assignment["index"]
        for assignment in assignments
        if assignment["weighted_audit_score"] < 0.72
        or assignment["sentence_end_similarity_audit"] < 0.50
        or assignment["sentence_kana_similarity_audit"] < 0.60
    ]
    if weak_indexes:
        debug_result["failure_reason"] = "weak_assignment_scores"
        debug_result["weak_indexes"] = weak_indexes
        return debug_result

    debug_result["audit_decision"] = "auto_approved"
    return debug_result


def generate_run_candidates(
    entry: dict[str, Any],
    track_path: str,
    atomic_chunks: list[tuple[float, float]],
    chunk_idx: int,
    transcriber: TranscriptionBackend,
    clip_cache: dict[str, str],
    run: dict[str, Any],
) -> list[dict[str, Any]]:
    """Generate candidate windows for one item inside a bounded run.

    The generator tries two shapes because the book audio commonly follows one
    of two patterns:

    - same-segment: the spoken word and sentence form one contiguous utterance
    - split-segment: the word is spoken first, followed by the sentence

    Args:
        entry: Vocabulary entry being matched.
        track_path: Source audio track.
        atomic_chunks: Silence-bounded chunks inside the bounded run.
        chunk_idx: Current chunk position for candidate generation.
        transcriber: Active ASR backend.
        clip_cache: Transcript cache reused across windows.
        run: Metadata about the bounded run and its anchor items.

    Returns:
        Candidate assignment dictionaries ready for scoring and DP.
    """

    candidates: list[dict[str, Any]] = []
    reading_hira = phonetic_hiragana(entry.get("reading") or entry.get("headword_text"))
    sentence_hira = phonetic_hiragana(entry.get("sentence_text"))

    for word_len in (1, 2):
        word_end_idx = chunk_idx + word_len - 1
        if word_end_idx >= len(atomic_chunks):
            continue
        word_start = atomic_chunks[chunk_idx][0]
        word_end = atomic_chunks[word_end_idx][1]
        word_text = transcribe_audio_window(track_path, word_start, word_end, transcriber, clip_cache)

        # same_segment: sentence window includes the initial word portion
        for total_len in range(word_len, min(5, len(atomic_chunks) - chunk_idx) + 1):
            same_end_idx = chunk_idx + total_len - 1
            sentence_start = atomic_chunks[chunk_idx][0]
            sentence_end = atomic_chunks[same_end_idx][1]
            sentence_text = transcribe_audio_window(track_path, sentence_start, sentence_end, transcriber, clip_cache)
            candidate = build_window_candidate(
                transcript_excerpt=f"{word_text} / {sentence_text}".strip(" /"),
                word_text=word_text,
                sentence_text=sentence_text,
                reading_hira=reading_hira,
                expected_sentence_hira=sentence_hira,
                word_start=word_start,
                word_end=word_end,
                sentence_start=sentence_start,
                sentence_end=sentence_end,
                matching_mode="bounded_run_same_segment",
                anchor_supported=True,
                audit_reason="bounded_run_same_segment",
                track_path=track_path,
                prev_index=run["prev_anchor"]["index"],
                next_index=run["next_anchor"]["index"],
            )
            candidate["index"] = entry["index"]
            candidate["next_chunk_index"] = same_end_idx + 1
            candidate["solver_type"] = "bounded_run_openai"
            candidate["run_start"] = run["run_start"]
            candidate["run_end"] = run["run_end"]
            candidate["anchor_prev_index"] = run["prev_anchor"]["index"]
            candidate["anchor_next_index"] = run["next_anchor"]["index"]
            candidate["openai_whisper_word_transcript"] = word_text
            candidate["openai_whisper_sentence_transcript"] = sentence_text
            candidates.append(candidate)

        # split_segment: sentence starts after the word window
        sentence_start_idx = word_end_idx + 1
        if sentence_start_idx >= len(atomic_chunks):
            continue
        for sentence_len in range(1, min(4, len(atomic_chunks) - sentence_start_idx) + 1):
            total_chunks = word_len + sentence_len
            if total_chunks > 5:
                continue
            sentence_end_idx = sentence_start_idx + sentence_len - 1
            sentence_start = atomic_chunks[sentence_start_idx][0]
            sentence_end = atomic_chunks[sentence_end_idx][1]
            sentence_text = transcribe_audio_window(track_path, sentence_start, sentence_end, transcriber, clip_cache)
            candidate = build_window_candidate(
                transcript_excerpt=f"{word_text} / {sentence_text}",
                word_text=word_text,
                sentence_text=sentence_text,
                reading_hira=reading_hira,
                expected_sentence_hira=sentence_hira,
                word_start=word_start,
                word_end=word_end,
                sentence_start=sentence_start,
                sentence_end=sentence_end,
                matching_mode="bounded_run_split_segment",
                anchor_supported=True,
                audit_reason="bounded_run_split_segment",
                track_path=track_path,
                prev_index=run["prev_anchor"]["index"],
                next_index=run["next_anchor"]["index"],
            )
            candidate["index"] = entry["index"]
            candidate["next_chunk_index"] = sentence_end_idx + 1
            candidate["solver_type"] = "bounded_run_openai"
            candidate["run_start"] = run["run_start"]
            candidate["run_end"] = run["run_end"]
            candidate["anchor_prev_index"] = run["prev_anchor"]["index"]
            candidate["anchor_next_index"] = run["next_anchor"]["index"]
            candidate["openai_whisper_word_transcript"] = word_text
            candidate["openai_whisper_sentence_transcript"] = sentence_text
            candidates.append(candidate)

    return candidates


def strip_next_chunk_index(candidate: dict[str, Any]) -> dict[str, Any]:
    """Remove DP-only state from a candidate before serializing it.

    Args:
        candidate: Candidate dictionary produced during bounded-run solving.

    Returns:
        The same dictionary without the internal ``next_chunk_index`` field.
    """

    candidate.pop("next_chunk_index", None)
    return candidate


def promote_run_assignment(
    manifest: list[dict[str, Any]],
    combined_by_index: dict[int, dict[str, Any]],
    assignment: dict[str, Any],
) -> dict[str, Any]:
    """Promote a bounded-run assignment into the main project outputs.

    Promotion means more than changing a flag. The function also:

    - cuts final ``wordN.mp3`` and ``sentenceN.mp3`` clips
    - updates the manifest row
    - updates the combined vocabulary entry's ``audio`` block

    Args:
        manifest: Full alignment manifest to mutate in place.
        combined_by_index: Combined vocabulary entries keyed by index.
        assignment: Auto-approved bounded-run assignment.

    Returns:
        The normalized manifest row that was written back.
    """

    item = item_by_index(manifest, assignment["index"])
    entry = combined_by_index[assignment["index"]]
    unit_number = entry.get("unit", {}).get("number") or item.get("unit_number")
    clip_dir = ROOT / "output" / "clips" / f"unit{int(unit_number):02d}"
    clip_dir.mkdir(parents=True, exist_ok=True)
    word_clip_path = clip_dir / f"word{assignment['index']}.mp3"
    sentence_clip_path = clip_dir / f"sentence{assignment['index']}.mp3"
    source_audio = ROOT / assignment["track_path"]
    cut_audio_clip(source_audio, word_clip_path, assignment["word_start"], assignment["word_end"])
    cut_audio_clip(source_audio, sentence_clip_path, assignment["sentence_start"], assignment["sentence_end"])

    promoted_row = {
        "index": assignment["index"],
        "unit_number": unit_number,
        "track_path": assignment["track_path"],
        "track_name": assignment["track_name"],
        "track_number": track_sort_key(Path(assignment["track_path"])),
        "word_start": round(assignment["word_start"], 4),
        "word_end": round(assignment["word_end"], 4),
        "sentence_start": round(assignment["sentence_start"], 4),
        "sentence_end": round(assignment["sentence_end"], 4),
        "word_clip_path": str(word_clip_path.relative_to(ROOT)),
        "sentence_clip_path": str(sentence_clip_path.relative_to(ROOT)),
        "word_confidence": round(assignment["word_reading_similarity_audit"], 4),
        "sentence_confidence": round(assignment["sentence_kana_similarity_audit"], 4),
        "confidence": round(assignment["weighted_audit_score"], 4),
        "needs_review": False,
        "review_reasons": [],
        "transcript_excerpt": assignment["transcript_excerpt"],
        "matching_mode": assignment["matching_mode"],
    }
    item.update(promoted_row)
    entry["audio"] = {
        "track_path": promoted_row["track_path"],
        "track_name": promoted_row["track_name"],
        "track_number": promoted_row["track_number"],
        "word_start": promoted_row["word_start"],
        "word_end": promoted_row["word_end"],
        "sentence_start": promoted_row["sentence_start"],
        "sentence_end": promoted_row["sentence_end"],
        "word_clip_path": promoted_row["word_clip_path"],
        "sentence_clip_path": promoted_row["sentence_clip_path"],
        "confidence": promoted_row["confidence"],
        "word_confidence": promoted_row["word_confidence"],
        "sentence_confidence": promoted_row["sentence_confidence"],
        "needs_review": False,
        "review_reasons": [],
        "transcript_excerpt": promoted_row["transcript_excerpt"],
        "matching_mode": promoted_row["matching_mode"],
    }
    return promoted_row


def build_run_audit_result(
    original_item: dict[str, Any],
    entry: dict[str, Any],
    assignment: dict[str, Any],
    run_result: dict[str, Any],
) -> dict[str, Any]:
    """Build the exported audit record for an auto-approved bounded-run item.

    Args:
        original_item: Review item before promotion.
        entry: Combined vocabulary entry.
        assignment: Winning bounded-run assignment.
        run_result: Parent bounded-run solver result.

    Returns:
        A JSON-ready audit record with scores, clips, and provenance fields.
    """

    return {
        "index": assignment["index"],
        "word": entry.get("headword_text") or entry.get("kanji") or entry.get("reading") or "",
        "reading": entry.get("reading") or "",
        "sentence_1": entry.get("sentence_text") or "",
        "track_name": assignment["track_name"],
        "track_path": assignment["track_path"],
        "matching_mode": assignment["matching_mode"],
        "review_reasons": original_item.get("review_reasons", []),
        "transcript_excerpt": assignment["transcript_excerpt"],
        "confidence": round(assignment["weighted_audit_score"], 4),
        "word_confidence": round(assignment["word_reading_similarity_audit"], 4),
        "sentence_confidence": round(assignment["sentence_kana_similarity_audit"], 4),
        "word_similarity_audit": round(assignment["word_reading_similarity_audit"], 4),
        "sentence_similarity_audit": round(assignment["sentence_kana_similarity_audit"], 4),
        "word_reading_similarity_audit": round(assignment["word_reading_similarity_audit"], 4),
        "sentence_kana_similarity_audit": round(assignment["sentence_kana_similarity_audit"], 4),
        "sentence_start_similarity_audit": round(assignment["sentence_start_similarity_audit"], 4),
        "sentence_end_similarity_audit": round(assignment["sentence_end_similarity_audit"], 4),
        "length_ratio_score_audit": round(assignment["length_ratio_score_audit"], 4),
        "weighted_audit_score": round(assignment["weighted_audit_score"], 4),
        "exact_word_hit": False,
        "monotonic_neighbor_support": True,
        "boundary_anchor_score": 1.0,
        "boundary_anchor_reasons": [
            f"after_verified_{run_result['anchor_prev_index']}",
            f"before_verified_{run_result['anchor_next_index']}",
        ],
        "prev_index": run_result["anchor_prev_index"],
        "next_index": run_result["anchor_next_index"],
        "word_clip_path": f"output/clips/unit{int(entry.get('unit', {}).get('number') or original_item.get('unit_number')):02d}/word{assignment['index']}.mp3",
        "sentence_clip_path": f"output/clips/unit{int(entry.get('unit', {}).get('number') or original_item.get('unit_number')):02d}/sentence{assignment['index']}.mp3",
        "openai_whisper_word_transcript": assignment.get("openai_whisper_word_transcript", ""),
        "openai_whisper_sentence_transcript": assignment.get("openai_whisper_sentence_transcript", ""),
        "openai_whisper_word_similarity": round(assignment["word_reading_similarity_audit"], 4),
        "openai_whisper_sentence_similarity": round(assignment["sentence_kana_similarity_audit"], 4),
        "openai_whisper_sentence_start_similarity": round(assignment["sentence_start_similarity_audit"], 4),
        "openai_whisper_sentence_end_similarity": round(assignment["sentence_end_similarity_audit"], 4),
        "openai_whisper_length_ratio": round(assignment["length_ratio_score_audit"], 4),
        "audit_decision": "auto_approved",
        "audit_reasons": assignment["audit_reasons"],
        "solver_type": "bounded_run_openai",
        "run_start": run_result["run_start"],
        "run_end": run_result["run_end"],
        "anchor_prev_index": run_result["anchor_prev_index"],
        "anchor_next_index": run_result["anchor_next_index"],
        "rescue_candidate": strip_next_chunk_index(dict(assignment)),
    }


def audit_item(
    manifest: list[dict[str, Any]],
    pos: int,
    item: dict[str, Any],
    entry: dict[str, Any],
    whisper_model: WhisperModel,
    transcriber: TranscriptionBackend,
    track_cache: dict[str, list[TrackSegment]],
    clip_cache: dict[str, str],
    manual_verified_indexes: set[int],
    trusted_indexes: set[int],
    silence_cache: dict[str, list[tuple[float, float]]],
) -> dict[str, Any]:
    """Audit one manifest item that still needs review.

    This function is the main per-item judge. It combines several evidence
    sources:

    - original manifest transcript
    - kana/hiragana-normalized similarity
    - sentence start/end similarity
    - clip-level retranscription
    - neighbor-order support
    - bounded-gap rescue for unmatched items

    Args:
        manifest: Full alignment manifest.
        pos: Position of the item in ``manifest``.
        item: Current manifest row under review.
        entry: Matching vocabulary entry from the combined JSON.
        whisper_model: Faster Whisper model used for full-track rescue.
        transcriber: Active backend for clip/window transcription.
        track_cache: Cache of full-track ASR segments.
        clip_cache: Cache of clip/window transcripts.
        manual_verified_indexes: User-confirmed indexes that should be trusted.
        trusted_indexes: All trusted indexes known at this point in the pass.
        silence_cache: Cache of silence chunks by track.

    Returns:
        A JSON-ready audit record for this item.
    """

    # We treat the book index and track-local ordering as trusted structure.
    # The transcript itself is only weak evidence because ASR often confuses
    # semantically similar or phonetically close tokens.
    #
    # For items that already have a candidate match, we audit that candidate.
    # For `no_matching_track_content`, we attempt a rescue pass below.
    transcript = item.get("transcript_excerpt") or ""
    headword = entry.get("headword_text") or entry.get("kanji") or entry.get("reading") or ""
    reading = entry.get("reading") or ""
    sentence = entry.get("sentence_text") or ""
    transcript_word_part, transcript_sentence_part = split_transcript_parts(transcript, item.get("matching_mode"))

    # Build phonetic versions of the truth and transcript. This lets us compare
    # "夫婦" with "ふふ" or "仲がいい" with "なかがいい" without over-penalizing
    # kanji/kana representation differences.
    reading_kana = phonetic_hiragana(reading or headword)
    sentence_kana = phonetic_hiragana(sentence)
    transcript_word_kana = phonetic_hiragana(transcript_word_part)
    transcript_sentence_kana = phonetic_hiragana(transcript_sentence_part or transcript)

    # Two kinds of textual evidence:
    # - word_similarity: can the transcript plausibly contain the target word?
    # - sentence_similarity: does the transcript plausibly match sentence 1?
    #
    # In practice, sentence similarity is the stronger signal because it has
    # more content and is therefore less ambiguous than a short isolated word.
    word_similarity = max(similarity(headword, transcript), similarity(reading, transcript))
    sentence_similarity = similarity(sentence, transcript)
    exact_word_hit = contains_normalized(transcript, headword) or contains_normalized(transcript, reading)
    word_reading_similarity = similarity(reading_kana, transcript_word_kana or transcript_sentence_kana)
    sentence_kana_similarity = similarity(sentence_kana, transcript_sentence_kana)
    sentence_start_similarity = boundary_similarity(sentence_kana, transcript_sentence_kana, side="start")
    sentence_end_similarity = boundary_similarity(sentence_kana, transcript_sentence_kana, side="end")
    length_ratio_score = ratio_score(sentence_kana, transcript_sentence_kana)

    prev_item = manifest[pos - 1] if pos > 0 else None
    next_item = manifest[pos + 1] if pos + 1 < len(manifest) else None
    monotonic_neighbors = has_monotonic_neighbor_support(prev_item, item, next_item)
    neighbor_score = 1.0 if monotonic_neighbors else 0.0
    boundary_anchor_score, boundary_anchor_reasons = compute_boundary_anchor_score(
        manifest=manifest,
        pos=pos,
        item=item,
        trusted_indexes=trusted_indexes,
    )

    # OpenAI Whisper is used as a second opinion only on the already cut clips.
    # This keeps the expensive pass bounded to review items, and it answers a
    # different question than the track-level rescue pass:
    # "Given the exact word clip and sentence clip we already cut, do they look
    #  good enough when transcribed independently?"
    clip_transcript = transcribe_review_clips(item, transcriber, clip_cache)
    clip_word_similarity = similarity(reading_kana, clip_transcript.word_hira)
    clip_sentence_similarity = similarity(sentence_kana, clip_transcript.sentence_hira)
    clip_sentence_start = boundary_similarity(sentence_kana, clip_transcript.sentence_hira, side="start")
    clip_sentence_end = boundary_similarity(sentence_kana, clip_transcript.sentence_hira, side="end")
    clip_length_ratio = ratio_score(sentence_kana, clip_transcript.sentence_hira)

    # Weighted audit score: 6 sub-signals, all in [0, 1].
    # Word reading and sentence kana are the core identity signals.
    # Start/end boundary similarity gets equal weight because in practice
    # a clip that sounds right in the middle but is cut at the wrong point
    # usually fails on boundary similarity first — this catches most off-by-one
    # silence-window errors. Length ratio and neighbor support are tie-breakers;
    # they rarely flip the result on their own but prevent auto-approval of
    # clips that are dramatically too short or floating free of their neighbors.
    final_score = (
        0.20 * word_reading_similarity
        + 0.20 * sentence_kana_similarity
        + 0.20 * sentence_start_similarity
        + 0.20 * sentence_end_similarity
        + 0.10 * length_ratio_score
        + 0.10 * neighbor_score
    )

    # This second-pass audit is intentionally conservative:
    # - it never overrides missing-audio / no-track cases
    # - it only auto-approves when either the local track position is strongly
    #   supported by neighbors, or the transcript is a very good textual match
    audit_reasons: list[str] = []
    decision = "needs_human_review"
    if item["index"] in manual_verified_indexes:
        decision = "auto_approved"
        audit_reasons.append("manual_verified")
    if item.get("track_name"):
        # Rule 1:
        # If the item sits cleanly between its neighbors on the same track,
        # and the word is explicitly present, we can accept a moderate sentence
        # similarity. This is the "長男" style case from the discussion.
        if decision != "auto_approved" and monotonic_neighbors and sentence_end_similarity >= 0.72 and word_reading_similarity >= 0.45:
            decision = "auto_approved"
            audit_reasons.append("monotonic_neighbors+strong_sentence_end+reading_similarity")
        elif decision != "auto_approved" and monotonic_neighbors and sentence_kana_similarity >= 0.62 and exact_word_hit:
            decision = "auto_approved"
            audit_reasons.append("monotonic_neighbors+exact_word+sentence_kana_similarity")
        # Rule 2:
        # Strong sentence similarity plus trustworthy local position can rescue
        # cases where the word itself was badly misheard.
        elif decision != "auto_approved" and monotonic_neighbors and sentence_kana_similarity >= 0.72 and length_ratio_score >= 0.75:
            decision = "auto_approved"
            audit_reasons.append("monotonic_neighbors+strong_sentence_kana_similarity")
        # Rule 3:
        # Even without neighbor support, an exact word hit plus strong sentence
        # similarity is usually enough to accept the match.
        elif decision != "auto_approved" and exact_word_hit and sentence_end_similarity >= 0.76 and sentence_start_similarity >= 0.55:
            decision = "auto_approved"
            audit_reasons.append("exact_word+boundary_weighted_sentence_similarity")
        # Rule 4:
        # For split-segment cases we expect the word segment to be especially
        # clean, so we require a stronger word similarity.
        elif (
            decision != "auto_approved"
            and item.get("matching_mode") == "split_segment"
            and word_reading_similarity >= 0.62
            and sentence_end_similarity >= 0.62
            and length_ratio_score >= 0.70
        ):
            decision = "auto_approved"
            audit_reasons.append("split_segment+reading_and_sentence_end_similarity")
        elif decision != "auto_approved" and final_score >= 0.70 and monotonic_neighbors and sentence_end_similarity >= 0.60:
            decision = "auto_approved"
            audit_reasons.append("weighted_score+monotonic_neighbors")
        # Rule 5:
        # If clip-level OpenAI Whisper says the isolated sentence clip matches
        # well and the timing is cleanly bounded by trusted neighbors, allow
        # that to auto-approve even when the original merged transcript was weak.
        elif (
            decision != "auto_approved"
            and clip_sentence_end >= 0.80
            and clip_sentence_similarity >= 0.82
            and clip_length_ratio >= 0.85
            and boundary_anchor_score >= 0.5
        ):
            decision = "auto_approved"
            audit_reasons.append("openai_clip_sentence+trusted_boundary_anchor")
        elif (
            decision != "auto_approved"
            and clip_sentence_similarity >= 0.88
            and clip_sentence_start >= 0.72
            and clip_sentence_end >= 0.72
            and clip_length_ratio >= 0.85
        ):
            decision = "auto_approved"
            audit_reasons.append("openai_clip_strong_sentence_match")

    rescue = None
    if decision != "auto_approved" and "no_matching_track_content" in (item.get("review_reasons") or []):
        rescue = rescue_unmatched_item(
            manifest=manifest,
            pos=pos,
            entry=entry,
            whisper_model=whisper_model,
            transcriber=transcriber,
            track_cache=track_cache,
            clip_cache=clip_cache,
            trusted_indexes=trusted_indexes,
            silence_cache=silence_cache,
        )
        if rescue and rescue["audit_decision"] == "auto_approved":
            decision = "auto_approved"
            audit_reasons = rescue["audit_reasons"]
            transcript = rescue["transcript_excerpt"]
            word_reading_similarity = rescue["word_reading_similarity_audit"]
            sentence_kana_similarity = rescue["sentence_kana_similarity_audit"]
            sentence_start_similarity = rescue["sentence_start_similarity_audit"]
            sentence_end_similarity = rescue["sentence_end_similarity_audit"]
            length_ratio_score = rescue["length_ratio_score_audit"]
            final_score = rescue["weighted_audit_score"]
            monotonic_neighbors = rescue["monotonic_neighbor_support"]
            prev_item = {"index": rescue["prev_index"]} if rescue["prev_index"] is not None else prev_item
            next_item = {"index": rescue["next_index"]} if rescue["next_index"] is not None else next_item

    result = {
        "index": item["index"],
        "word": headword,
        "reading": reading,
        "sentence_1": sentence,
        "track_name": item.get("track_name"),
        "track_path": item.get("track_path"),
        "matching_mode": item.get("matching_mode"),
        "review_reasons": item.get("review_reasons", []),
        "transcript_excerpt": transcript,
        "confidence": item.get("confidence"),
        "word_confidence": item.get("word_confidence"),
        "sentence_confidence": item.get("sentence_confidence"),
        "word_similarity_audit": round(word_similarity, 4),
        "sentence_similarity_audit": round(sentence_similarity, 4),
        "word_reading_similarity_audit": round(word_reading_similarity, 4),
        "sentence_kana_similarity_audit": round(sentence_kana_similarity, 4),
        "sentence_start_similarity_audit": round(sentence_start_similarity, 4),
        "sentence_end_similarity_audit": round(sentence_end_similarity, 4),
        "length_ratio_score_audit": round(length_ratio_score, 4),
        "weighted_audit_score": round(final_score, 4),
        "exact_word_hit": exact_word_hit,
        "monotonic_neighbor_support": monotonic_neighbors,
        "boundary_anchor_score": round(boundary_anchor_score, 4),
        "boundary_anchor_reasons": boundary_anchor_reasons,
        "prev_index": prev_item.get("index") if prev_item else None,
        "next_index": next_item.get("index") if next_item else None,
        "word_clip_path": item.get("word_clip_path"),
        "sentence_clip_path": item.get("sentence_clip_path"),
        "openai_whisper_word_transcript": clip_transcript.word_text,
        "openai_whisper_sentence_transcript": clip_transcript.sentence_text,
        "openai_whisper_word_similarity": round(clip_word_similarity, 4),
        "openai_whisper_sentence_similarity": round(clip_sentence_similarity, 4),
        "openai_whisper_sentence_start_similarity": round(clip_sentence_start, 4),
        "openai_whisper_sentence_end_similarity": round(clip_sentence_end, 4),
        "openai_whisper_length_ratio": round(clip_length_ratio, 4),
        "audit_decision": decision,
        "audit_reasons": audit_reasons,
        "solver_type": None,
        "run_start": None,
        "run_end": None,
        "anchor_prev_index": None,
        "anchor_next_index": None,
    }
    if rescue:
        result["rescue_candidate"] = rescue
        if rescue.get("solver_type"):
            result["solver_type"] = rescue.get("solver_type")
            result["run_start"] = rescue.get("run_start")
            result["run_end"] = rescue.get("run_end")
            result["anchor_prev_index"] = rescue.get("anchor_prev_index")
            result["anchor_next_index"] = rescue.get("anchor_next_index")
    return result


def rescue_unmatched_item(
    manifest: list[dict[str, Any]],
    pos: int,
    entry: dict[str, Any],
    whisper_model: WhisperModel,
    transcriber: TranscriptionBackend,
    track_cache: dict[str, list[TrackSegment]],
    clip_cache: dict[str, str],
    trusted_indexes: set[int],
    silence_cache: dict[str, list[tuple[float, float]]],
) -> dict[str, Any] | None:
    """Try to rescue an item that never received an initial track match.

    This is the fallback for ``no_matching_track_content``. It first tries the
    stronger bounded-gap solver when both neighboring anchors live on the same
    track. If that is not available, it falls back to a broader local-track
    search over coarse ASR segments.

    Args:
        manifest: Full alignment manifest.
        pos: Position of the unresolved item in ``manifest``.
        entry: Combined vocabulary entry for the unresolved item.
        whisper_model: Faster Whisper model used for whole-track segmentation.
        transcriber: Active backend for clip/window transcription.
        track_cache: Cache of full-track ASR segments.
        clip_cache: Cache of clip/window transcripts.
        trusted_indexes: Indexes already treated as reliable anchors.
        silence_cache: Cache of silence chunks by track.

    Returns:
        The best rescue candidate when one can be found, otherwise ``None``.
    """

    inferred = infer_track_from_neighbors(
        manifest,
        pos,
        entry.get("unit", {}).get("number"),
        trusted_indexes,
    )
    if not inferred:
        return None

    track_path, prev_item, next_item = inferred
    if prev_item and next_item and prev_item.get("track_path") == next_item.get("track_path") == track_path:
        bounded = rescue_bounded_gap_with_openai(
            entry=entry,
            track_path=track_path,
            prev_item=prev_item,
            next_item=next_item,
            transcriber=transcriber,
            clip_cache=clip_cache,
            silence_cache=silence_cache,
        )
        if bounded and bounded["audit_decision"] == "auto_approved":
            return bounded

    segments = get_track_segments(track_path, whisper_model, track_cache)
    if not segments:
        return None

    lower = prev_item.get("sentence_end") if prev_item and prev_item.get("track_path") == track_path else None
    upper = next_item.get("word_start") if next_item and next_item.get("track_path") == track_path else None

    # Search only the local gap between trusted neighbors when possible. This
    # uses the book index and track timeline as anchors to avoid searching the
    # entire track blindly.
    window = [
        seg
        for seg in segments
        if (lower is None or seg.end >= lower - 0.25) and (upper is None or seg.start <= upper + 0.25)
    ]
    if not window:
        window = segments

    candidates: list[dict[str, Any]] = []
    reading_hira = phonetic_hiragana(entry.get("reading") or entry.get("headword_text"))
    sentence_hira = phonetic_hiragana(entry.get("sentence_text"))
    exact_neighbor_support = bool(prev_item and next_item and prev_item.get("track_path") == next_item.get("track_path") == track_path)

    for start in range(len(window)):
        for length in (1, 2, 3):
            group = window[start : start + length]
            if len(group) != length:
                continue
            candidates.extend(score_segment_group(group, reading_hira, sentence_hira, exact_neighbor_support))

    if not candidates:
        return None

    best = max(candidates, key=lambda item: item["weighted_audit_score"])
    best["track_name"] = Path(track_path).name
    best["track_path"] = track_path
    best["prev_index"] = prev_item.get("index") if prev_item else None
    best["next_index"] = next_item.get("index") if next_item else None
    if best["weighted_audit_score"] >= 0.72 and best["sentence_end_similarity_audit"] >= 0.60:
        best["audit_decision"] = "auto_approved"
    else:
        best["audit_decision"] = "needs_human_review"
    return best


def score_segment_group(
    group: list[TrackSegment],
    reading_hira: str,
    sentence_hira: str,
    neighbor_support: bool,
) -> list[dict[str, Any]]:
    """Score several structural interpretations of one local segment group.

    Args:
        group: One to three neighboring ASR segments from a track.
        reading_hira: Expected word reading in hiragana.
        sentence_hira: Expected sentence in hiragana.
        neighbor_support: Whether trusted neighbors bracket the local area.

    Returns:
        Candidate score dictionaries for the possible word/sentence splits.
    """

    candidates: list[dict[str, Any]] = []
    joined_text = " / ".join(seg.text for seg in group)
    joined_hira = "".join(seg.hira for seg in group)

    # Candidate type 1: treat the whole group as one same-segment utterance.
    candidates.append(
        score_candidate(
            transcript_excerpt=joined_text,
            word_hira=joined_hira,
            sentence_hira_candidate=joined_hira,
            reading_hira=reading_hira,
            expected_sentence_hira=sentence_hira,
            matching_mode="rescue_same_segment",
            start=group[0].start,
            end=group[-1].end,
            neighbor_support=neighbor_support,
            audit_reason="rescue_same_segment",
        )
    )

    # Candidate type 2: first segment is the word, remaining segments form the sentence.
    if len(group) >= 2:
        word_part = group[0]
        sentence_part = group[1:]
        candidates.append(
            score_candidate(
                transcript_excerpt=f"{word_part.text} / {' / '.join(seg.text for seg in sentence_part)}",
                word_hira=word_part.hira,
                sentence_hira_candidate="".join(seg.hira for seg in sentence_part),
                reading_hira=reading_hira,
                expected_sentence_hira=sentence_hira,
                matching_mode="rescue_split_segment",
                start=group[0].start,
                end=group[-1].end,
                neighbor_support=neighbor_support,
                audit_reason="rescue_split_segment",
            )
        )

    # Candidate type 3: for 3-segment groups, sometimes the first two tiny
    # segments belong to the spoken word or sentence lead-in.
    if len(group) == 3:
        word_part = group[:2]
        sentence_part = group[2:]
        candidates.append(
            score_candidate(
                transcript_excerpt=f"{' / '.join(seg.text for seg in word_part)} / {sentence_part[0].text}",
                word_hira="".join(seg.hira for seg in word_part),
                sentence_hira_candidate="".join(seg.hira for seg in sentence_part),
                reading_hira=reading_hira,
                expected_sentence_hira=sentence_hira,
                matching_mode="rescue_split_2plus1",
                start=group[0].start,
                end=group[-1].end,
                neighbor_support=neighbor_support,
                audit_reason="rescue_split_2plus1",
            )
        )

    return candidates


def score_candidate(
    transcript_excerpt: str,
    word_hira: str,
    sentence_hira_candidate: str,
    reading_hira: str,
    expected_sentence_hira: str,
    matching_mode: str,
    start: float,
    end: float,
    neighbor_support: bool,
    audit_reason: str,
) -> dict[str, Any]:
    """Score one rescue candidate using the shared weighted audit formula.

    Args:
        transcript_excerpt: Human-readable text summary of the candidate.
        word_hira: Candidate word portion in hiragana.
        sentence_hira_candidate: Candidate sentence portion in hiragana.
        reading_hira: Expected word reading in hiragana.
        expected_sentence_hira: Expected sentence in hiragana.
        matching_mode: Label describing the candidate shape.
        start: Candidate start time.
        end: Candidate end time.
        neighbor_support: Whether neighboring trusted items support the timing.
        audit_reason: Rule label stored for later debugging.

    Returns:
        A candidate dictionary with all computed sub-scores and the final
        weighted score.
    """

    word_reading_similarity = similarity(reading_hira, word_hira)
    sentence_kana_similarity = similarity(expected_sentence_hira, sentence_hira_candidate)
    sentence_start_similarity = boundary_similarity(expected_sentence_hira, sentence_hira_candidate, side="start")
    sentence_end_similarity = boundary_similarity(expected_sentence_hira, sentence_hira_candidate, side="end")
    length_ratio_score = ratio_score(expected_sentence_hira, sentence_hira_candidate)
    weighted = (
        0.20 * word_reading_similarity
        + 0.20 * sentence_kana_similarity
        + 0.20 * sentence_start_similarity
        + 0.20 * sentence_end_similarity
        + 0.10 * length_ratio_score
        + 0.10 * (1.0 if neighbor_support else 0.0)
    )
    reasons = []
    if neighbor_support:
        reasons.append("neighbor_supported")
    reasons.append(audit_reason)
    return {
        "transcript_excerpt": transcript_excerpt,
        "matching_mode": matching_mode,
        "candidate_start": round(start, 4),
        "candidate_end": round(end, 4),
        "word_reading_similarity_audit": round(word_reading_similarity, 4),
        "sentence_kana_similarity_audit": round(sentence_kana_similarity, 4),
        "sentence_start_similarity_audit": round(sentence_start_similarity, 4),
        "sentence_end_similarity_audit": round(sentence_end_similarity, 4),
        "length_ratio_score_audit": round(length_ratio_score, 4),
        "weighted_audit_score": round(weighted, 4),
        "monotonic_neighbor_support": neighbor_support,
        "audit_reasons": reasons,
    }


def infer_track_from_neighbors(
    manifest: list[dict[str, Any]],
    pos: int,
    unit_number: int | None,
    trusted_indexes: set[int],
) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None] | None:
    """Infer the most likely track for an unresolved item from nearby anchors.

    Args:
        manifest: Full alignment manifest.
        pos: Position of the unresolved item.
        unit_number: Expected unit number, if known.
        trusted_indexes: Indexes already accepted as trustworthy.

    Returns:
        ``(track_path, prev_item, next_item)`` when inference succeeds,
        otherwise ``None``.
    """

    prev_item = None
    next_item = None

    for i in range(pos - 1, -1, -1):
        candidate = manifest[i]
        if not candidate.get("track_path"):
            continue
        if not is_trusted_anchor(candidate, trusted_indexes):
            continue
        if unit_number is not None:
            candidate_unit = infer_unit_from_track(candidate.get("track_path"))
            if candidate_unit != unit_number:
                break
        prev_item = candidate
        break

    for i in range(pos + 1, len(manifest)):
        candidate = manifest[i]
        if not candidate.get("track_path"):
            continue
        if not is_trusted_anchor(candidate, trusted_indexes):
            continue
        if unit_number is not None:
            candidate_unit = infer_unit_from_track(candidate.get("track_path"))
            if candidate_unit != unit_number:
                break
        next_item = candidate
        break

    if prev_item and next_item and prev_item.get("track_path") == next_item.get("track_path"):
        return prev_item["track_path"], prev_item, next_item
    if prev_item and next_item is None:
        return prev_item["track_path"], prev_item, None
    if next_item and prev_item is None:
        return next_item["track_path"], None, next_item
    if prev_item and next_item:
        # Conservative fallback: only use a one-sided anchor when the index gap
        # is small enough that a track boundary jump is unlikely.
        if pos - manifest.index(prev_item) <= 2:
            return prev_item["track_path"], prev_item, next_item
        if manifest.index(next_item) - pos <= 2:
            return next_item["track_path"], prev_item, next_item
    return None


def infer_unit_from_track(track_path: str | None) -> int | None:
    """Extract the unit number from a track path.

    Args:
        track_path: Relative track path such as ``audio/Unit1 名詞A/...``.

    Returns:
        The parsed unit number, or ``None`` when no unit marker is present.
    """

    if not track_path:
        return None
    match = re.search(r"Unit(\d+)", track_path)
    return int(match.group(1)) if match else None


def get_track_segments(
    track_path: str,
    whisper_model: WhisperModel,
    track_cache: dict[str, list[TrackSegment]],
) -> list[TrackSegment]:
    """Transcribe a full track into coarse ASR segments for the rescue pass.

    This is deliberately separate from the clip/window transcription backend
    (TranscriptionBackend). The rescue pass needs rough segment locations across
    an entire track to narrow down where a missing entry might live. faster_whisper
    with VAD filtering and beam_size=1 produces these coarse segments quickly
    in-process, without the subprocess startup cost of whisper.cpp per clip.

    The clip/window transcription uses the configured backend (openai or
    whisper_cpp) because per-clip accuracy matters more there — the rescue pass
    needs location, not perfection.

    condition_on_previous_text=False is important: without it, faster_whisper
    carries hallucinated context forward across segments of a long track, which
    produces cascading garbage segments for tracks longer than ~2 minutes.

    Args:
        track_path: Relative path to the source track.
        whisper_model: Loaded Faster Whisper model.
        track_cache: Cache of already transcribed tracks.

    Returns:
        A list of coarse track segments with both surface text and hiragana.
    """

    cached = track_cache.get(track_path)
    if cached is not None:
        return cached

    full_path = ROOT / track_path
    segments, _ = whisper_model.transcribe(
        str(full_path),
        language="ja",
        vad_filter=True,
        beam_size=1,
        condition_on_previous_text=False,
    )
    result: list[TrackSegment] = []
    for idx, seg in enumerate(segments):
        text = html.unescape(seg.text).strip()
        if not text:
            continue
        result.append(
            TrackSegment(
                index=idx,
                start=float(seg.start),
                end=float(seg.end),
                text=text,
                hira=phonetic_hiragana(text),
            )
        )
    track_cache[track_path] = result
    return result


def rescue_bounded_gap_with_openai(
    entry: dict[str, Any],
    track_path: str,
    prev_item: dict[str, Any],
    next_item: dict[str, Any],
    transcriber: TranscriptionBackend,
    clip_cache: dict[str, str],
    silence_cache: dict[str, list[tuple[float, float]]],
) -> dict[str, Any] | None:
    """Rescue one unresolved item when trusted neighbors bound its timeline.

    This is the stricter local solver used for "35 and 37 define 36"-style
    cases. It never searches the whole track. Instead, it enumerates only the
    silence-bounded windows between the trusted previous and next items.

    Args:
        entry: Combined vocabulary entry being rescued.
        track_path: Shared source track for the bounded gap.
        prev_item: Trusted previous manifest item.
        next_item: Trusted next manifest item.
        transcriber: Active backend for window transcription.
        clip_cache: Cache of window transcripts.
        silence_cache: Cache of silence chunks by track.

    Returns:
        The best bounded-gap candidate, or ``None`` when the gap is unsuitable.
    """

    # This is the stricter "35 and 37 define 36" style solver:
    # when trusted neighbors bracket the target on the same track, the target
    # must live inside that time gap. We therefore ignore the rest of the track
    # and only score silence-bounded candidates inside the bounded interval.
    lower = prev_item.get("sentence_end")
    upper = next_item.get("word_start")
    if lower is None or upper is None or upper <= lower:
        return None
    # Keep this solver focused on truly local gaps. Large gaps tend to contain
    # multiple unresolved items, and brute-forcing all chunk groupings there is
    # both expensive and less trustworthy than the generic rescue pass.
    if upper - lower > 12.0:
        return None

    chunks = get_silence_chunks(track_path, silence_cache)
    gap_chunks = [(start, end) for start, end in chunks if start >= lower - 0.05 and end <= upper + 0.05]
    if not gap_chunks:
        return None
    if len(gap_chunks) > 6:
        return None

    reading_hira = phonetic_hiragana(entry.get("reading") or entry.get("headword_text"))
    sentence_hira = phonetic_hiragana(entry.get("sentence_text"))
    candidates: list[dict[str, Any]] = []

    for start_idx in range(len(gap_chunks)):
        for end_idx in range(start_idx, min(len(gap_chunks), start_idx + 4)):
            group = gap_chunks[start_idx : end_idx + 1]
            # Same-segment interpretation: a single continuous utterance that
            # contains both the word and the sentence.
            whole_text = transcribe_audio_window(track_path, group[0][0], group[-1][1], transcriber, clip_cache)
            whole_hira = phonetic_hiragana(whole_text)
            candidates.append(
                build_window_candidate(
                    transcript_excerpt=whole_text,
                    word_text=whole_text,
                    sentence_text=whole_text,
                    reading_hira=reading_hira,
                    expected_sentence_hira=sentence_hira,
                    word_start=group[0][0],
                    word_end=group[0][1],
                    sentence_start=group[0][0],
                    sentence_end=group[-1][1],
                    matching_mode="bounded_gap_same_segment",
                    anchor_supported=True,
                    audit_reason="bounded_gap_same_segment",
                    track_path=track_path,
                    prev_index=prev_item.get("index"),
                    next_index=next_item.get("index"),
                )
            )

            # Split interpretation: first chunk(s) are the word, remaining
            # chunk(s) are the sentence. This matches the book/audio pattern.
            if len(group) >= 2:
                for split_at in range(1, len(group)):
                    word_group = group[:split_at]
                    sentence_group = group[split_at:]
                    word_text = transcribe_audio_window(track_path, word_group[0][0], word_group[-1][1], transcriber, clip_cache)
                    sentence_text = transcribe_audio_window(
                        track_path, sentence_group[0][0], sentence_group[-1][1], transcriber, clip_cache
                    )
                    candidates.append(
                        build_window_candidate(
                            transcript_excerpt=f"{word_text} / {sentence_text}".strip(" /"),
                            word_text=word_text,
                            sentence_text=sentence_text,
                            reading_hira=reading_hira,
                            expected_sentence_hira=sentence_hira,
                            word_start=word_group[0][0],
                            word_end=word_group[-1][1],
                            sentence_start=sentence_group[0][0],
                            sentence_end=sentence_group[-1][1],
                            matching_mode="bounded_gap_split_segment",
                            anchor_supported=True,
                            audit_reason="bounded_gap_split_segment",
                            track_path=track_path,
                            prev_index=prev_item.get("index"),
                            next_index=next_item.get("index"),
                        )
                    )

    if not candidates:
        return None

    best = max(candidates, key=lambda item: item["weighted_audit_score"])
    # Gap-bounded candidates are stronger than generic rescue because both
    # sides are pinned by trusted neighbors. That allows slightly lower word
    # scores when the sentence match is strong and the boundaries fit cleanly.
    if (
        best["weighted_audit_score"] >= 0.72
        and best["sentence_end_similarity_audit"] >= 0.50
        and best["sentence_kana_similarity_audit"] >= 0.60
    ):
        best["audit_decision"] = "auto_approved"
    else:
        best["audit_decision"] = "needs_human_review"
    return best


def build_window_candidate(
    transcript_excerpt: str,
    word_text: str,
    sentence_text: str,
    reading_hira: str,
    expected_sentence_hira: str,
    word_start: float,
    word_end: float,
    sentence_start: float,
    sentence_end: float,
    matching_mode: str,
    anchor_supported: bool,
    audit_reason: str,
    track_path: str,
    prev_index: int | None,
    next_index: int | None,
) -> dict[str, Any]:
    """Score a silence-bounded candidate window.

    Args:
        transcript_excerpt: Human-readable summary of the candidate text.
        word_text: Candidate word portion as transcribed.
        sentence_text: Candidate sentence portion as transcribed.
        reading_hira: Expected word reading in hiragana.
        expected_sentence_hira: Expected sentence in hiragana.
        word_start: Start time of the word clip.
        word_end: End time of the word clip.
        sentence_start: Start time of the sentence clip.
        sentence_end: End time of the sentence clip.
        matching_mode: Label describing the candidate shape.
        anchor_supported: Whether trusted neighbors support the timing.
        audit_reason: Rule label stored for later inspection.
        track_path: Source track path.
        prev_index: Previous anchor index when known.
        next_index: Next anchor index when known.

    Returns:
        A fully scored candidate dictionary.
    """

    word_hira = phonetic_hiragana(word_text)
    sentence_hira_candidate = phonetic_hiragana(sentence_text)
    word_reading_similarity = similarity(reading_hira, word_hira)
    sentence_kana_similarity = similarity(expected_sentence_hira, sentence_hira_candidate)
    sentence_start_similarity = boundary_similarity(expected_sentence_hira, sentence_hira_candidate, side="start")
    sentence_end_similarity = boundary_similarity(expected_sentence_hira, sentence_hira_candidate, side="end")
    length_ratio_score = ratio_score(expected_sentence_hira, sentence_hira_candidate)
    weighted = (
        0.20 * word_reading_similarity
        + 0.20 * sentence_kana_similarity
        + 0.20 * sentence_start_similarity
        + 0.20 * sentence_end_similarity
        + 0.10 * length_ratio_score
        + 0.10 * (1.0 if anchor_supported else 0.0)
    )
    reasons = []
    if anchor_supported:
        reasons.append("bounded_by_trusted_neighbors")
    reasons.append(audit_reason)
    return {
        "transcript_excerpt": transcript_excerpt,
        "matching_mode": matching_mode,
        "candidate_start": round(word_start, 4),
        "candidate_end": round(sentence_end, 4),
        "word_start": round(word_start, 4),
        "word_end": round(word_end, 4),
        "sentence_start": round(sentence_start, 4),
        "sentence_end": round(sentence_end, 4),
        "word_reading_similarity_audit": round(word_reading_similarity, 4),
        "sentence_kana_similarity_audit": round(sentence_kana_similarity, 4),
        "sentence_start_similarity_audit": round(sentence_start_similarity, 4),
        "sentence_end_similarity_audit": round(sentence_end_similarity, 4),
        "length_ratio_score_audit": round(length_ratio_score, 4),
        "weighted_audit_score": round(weighted, 4),
        "monotonic_neighbor_support": anchor_supported,
        "audit_reasons": reasons,
        "track_name": Path(track_path).name,
        "track_path": track_path,
        "prev_index": prev_index,
        "next_index": next_index,
    }


def get_silence_chunks(
    track_path: str,
    silence_cache: dict[str, list[tuple[float, float]]],
) -> list[tuple[float, float]]:
    """Split a track into speech chunks using ``ffmpeg`` silence detection.

    Uses the same -32dB noise floor as the main pipeline. The duration threshold
    is 0.18s here (vs the recommended 0.25s in align_track_by_llm). The audit
    pass uses slightly shorter silence windows because it is scanning for any
    candidate boundary inside a small gap; a stricter 0.25s would miss genuine
    very-short pauses between entries that are close together.

    Args:
        track_path: Relative source track path.
        silence_cache: Cache of already detected silence chunks.

    Returns:
        A list of ``(start, end)`` speech windows in seconds.
    """

    cached = silence_cache.get(track_path)
    if cached is not None:
        return cached

    full_path = ROOT / track_path
    result = subprocess.run(
        [
            "ffmpeg",
            "-i",
            str(full_path),
            "-af",
            "silencedetect=noise=-32dB:d=0.18",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    lines = result.stderr.splitlines()
    chunks: list[tuple[float, float]] = []
    current_start = 0.0
    for line in lines:
        if "silence_end:" in line:
            silence_end = float(line.split("silence_end:", 1)[1].split("|", 1)[0].strip())
            if silence_end > current_start:
                current_start = silence_end
        elif "silence_start:" in line:
            silence_start = float(line.split("silence_start:", 1)[1].strip())
            if silence_start > current_start:
                chunks.append((round(current_start, 4), round(silence_start, 4)))
    silence_cache[track_path] = chunks
    return chunks


def transcribe_audio_window(
    track_path: str,
    start: float,
    end: float,
    transcriber: TranscriptionBackend,
    clip_cache: dict[str, str],
) -> str:
    """Transcribe one bounded time range from a source track.

    The implementation cuts a temporary mono/16k WAV from the large track,
    transcribes that window, and caches the result. This is a practical
    compromise: the scoring logic can work in precise time ranges while the
    backends still receive normal audio files.

    Args:
        track_path: Relative path to the source track.
        start: Window start time in seconds.
        end: Window end time in seconds.
        transcriber: Active backend for transcription.
        clip_cache: Cache for already transcribed windows.

    Returns:
        The transcript text for the requested window.
    """

    cache_key = f"{track_path}::{start:.4f}-{end:.4f}"
    cached = clip_cache.get(cache_key)
    if cached is not None:
        return cached

    full_path = ROOT / track_path
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        temp_path = tmp.name
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                str(start),
                "-to",
                str(end),
                "-i",
                str(full_path),
                "-ac",
                "1",
                "-ar",
                "16000",
                temp_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        text = transcribe_file(temp_path, transcriber)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    clip_cache[cache_key] = text
    return text


def has_monotonic_neighbor_support(
    prev_item: dict[str, Any] | None,
    item: dict[str, Any],
    next_item: dict[str, Any] | None,
) -> bool:
    """Check whether an item sits in correct time order between its neighbors.

    Args:
        prev_item: Previous manifest item when available.
        item: Current manifest item.
        next_item: Next manifest item when available.

    Returns:
        ``True`` when the current item is cleanly bracketed in time on the same
        track, otherwise ``False``.
    """

    # This is the "order is truth" idea turned into code.
    # We only claim neighbor support when:
    # - previous/current/next items all live on the same track
    # - all necessary timestamps exist
    # - the current item's audio window falls strictly between its neighbors
    #
    # When that pattern holds, the timeline itself becomes evidence that the
    # current match is positioned where the book order says it should be.
    if not prev_item or not next_item:
        return False
    if not (
        prev_item.get("track_name")
        and item.get("track_name")
        and next_item.get("track_name")
        and prev_item.get("track_name") == item.get("track_name") == next_item.get("track_name")
    ):
        return False
    if (
        prev_item.get("sentence_end") is None
        or item.get("word_start") is None
        or item.get("sentence_end") is None
        or next_item.get("word_start") is None
    ):
        return False
    return prev_item["sentence_end"] <= item["word_start"] <= item["sentence_end"] <= next_item["word_start"]


def compute_boundary_anchor_score(
    manifest: list[dict[str, Any]],
    pos: int,
    item: dict[str, Any],
    trusted_indexes: set[int],
) -> tuple[float, list[str]]:
    """Measure how strongly trusted neighbors constrain an item's boundaries.

    Args:
        manifest: Full alignment manifest.
        pos: Position of the current item.
        item: Current manifest row.
        trusted_indexes: Indexes already accepted as trustworthy.

    Returns:
        A tuple of ``(score, reasons)`` where the score is ``0.0``, ``0.5``,
        or ``1.0``.
    """

    # A verified or already-accepted neighbor gives us a hard timing boundary.
    # That matters because once an item is known-correct, its end/start silence
    # points constrain where the neighboring item can realistically live.
    if item.get("word_start") is None or item.get("sentence_end") is None:
        return 0.0, []

    prev_anchor = find_nearest_trusted_neighbor(manifest, pos, direction=-1, trusted_indexes=trusted_indexes)
    next_anchor = find_nearest_trusted_neighbor(manifest, pos, direction=1, trusted_indexes=trusted_indexes)
    score = 0.0
    reasons: list[str] = []

    if (
        prev_anchor
        and prev_anchor.get("track_name")
        and item.get("track_name")
        and prev_anchor.get("track_name") == item.get("track_name")
        and prev_anchor.get("sentence_end") is not None
        and prev_anchor["sentence_end"] <= item["word_start"]
    ):
        score += 0.5
        reasons.append(f"after_verified_{prev_anchor['index']}")

    if (
        next_anchor
        and next_anchor.get("track_name")
        and item.get("track_name")
        and next_anchor.get("track_name") == item.get("track_name")
        and next_anchor.get("word_start") is not None
        and item["sentence_end"] <= next_anchor["word_start"]
    ):
        score += 0.5
        reasons.append(f"before_verified_{next_anchor['index']}")

    return score, reasons


def find_nearest_trusted_neighbor(
    manifest: list[dict[str, Any]],
    pos: int,
    direction: int,
    trusted_indexes: set[int],
) -> dict[str, Any] | None:
    """Walk left or right until a trusted manifest item is found.

    Args:
        manifest: Full alignment manifest.
        pos: Starting position.
        direction: ``-1`` for left, ``1`` for right.
        trusted_indexes: Indexes already accepted as trustworthy.

    Returns:
        The nearest trusted neighbor in the requested direction, or ``None``.
    """

    index = pos + direction
    while 0 <= index < len(manifest):
        candidate = manifest[index]
        if is_trusted_anchor(candidate, trusted_indexes):
            return candidate
        index += direction
    return None


def is_trusted_anchor(item: dict[str, Any] | None, trusted_indexes: set[int]) -> bool:
    """Return whether a manifest item is currently trusted.

    Args:
        item: Candidate manifest row.
        trusted_indexes: Trusted global indexes.

    Returns:
        ``True`` when the row's index belongs to ``trusted_indexes``.
    """

    if not item:
        return False
    return item.get("index") in trusted_indexes


def track_sort_key(path: Path) -> int:
    """Extract the leading numeric track order from a file path.

    Args:
        path: Track file path.

    Returns:
        The numeric prefix used for sorting, or a large fallback value when the
        file name does not begin with a number.
    """

    match = TRACK_NUM_RE.match(path.name)
    if not match:
        return 10_000
    return int(match.group(1))


def cut_audio_clip(source_audio: Path, output_path: Path, start: float, end: float) -> None:
    """Cut a final MP3 clip from a larger source audio file.

    Args:
        source_audio: Full source audio path.
        output_path: Destination clip path.
        start: Clip start time in seconds.
        end: Clip end time in seconds.
    """

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source_audio),
            "-ss",
            f"{start:.4f}",
            "-to",
            f"{end:.4f}",
            "-c",
            "copy",
            str(output_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def write_review_candidates(
    manifest: list[dict[str, Any]],
    combined: list[dict[str, Any]],
    output_dir: Path,
) -> None:
    """Write reviewer-friendly exports derived from the current manifest.

    Args:
        manifest: Full alignment manifest.
        combined: Combined vocabulary entries.
        output_dir: Output directory for the review JSON files.
    """

    combined_by_index = {entry["index"]: entry for entry in combined}
    review_candidates = [item for item in manifest if item.get("needs_review")]
    review_with_text: list[dict[str, Any]] = []
    for item in review_candidates:
        entry = combined_by_index.get(item["index"], {})
        review_with_text.append(
            {
                "index": item["index"],
                "word": entry.get("headword_text") or entry.get("kanji") or entry.get("reading"),
                "reading": entry.get("reading"),
                "sentence_1": entry.get("sentence_text"),
                "unit_number": entry.get("unit", {}).get("number"),
                "page": entry.get("page"),
                "track_name": item.get("track_name"),
                "track_path": item.get("track_path"),
                "word_start": item.get("word_start"),
                "word_end": item.get("word_end"),
                "sentence_start": item.get("sentence_start"),
                "sentence_end": item.get("sentence_end"),
                "word_clip_path": item.get("word_clip_path"),
                "sentence_clip_path": item.get("sentence_clip_path"),
                "confidence": item.get("confidence"),
                "word_confidence": item.get("word_confidence"),
                "sentence_confidence": item.get("sentence_confidence"),
                "review_reasons": item.get("review_reasons", []),
                "transcript_excerpt": item.get("transcript_excerpt", ""),
                "matching_mode": item.get("matching_mode"),
            }
        )

    (output_dir / "review_candidates.json").write_text(
        json.dumps(review_candidates, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "review_candidates_with_text.json").write_text(
        json.dumps(review_with_text, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_manual_verified_indexes(path: Path) -> set[int]:
    """Load the persistent list of manually verified indexes.

    Args:
        path: JSON file path.

    Returns:
        A set of integer indexes the user has already confirmed manually.
    """

    if not path.exists():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        values = payload.get("indexes", [])
    else:
        values = payload
    return {int(value) for value in values}


def load_openai_whisper_cache(path: Path) -> dict[str, str]:
    """Load the reusable transcription cache from disk.

    Args:
        path: JSON cache path.

    Returns:
        A string-to-string mapping of cache key to transcript text.
    """

    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(key): str(value) for key, value in payload.items()}


def transcribe_review_clips(
    item: dict[str, Any],
    transcriber: TranscriptionBackend,
    clip_cache: dict[str, str],
) -> ClipTranscript:
    """Retranscribe the already-cut word and sentence clips for one item.

    Args:
        item: Manifest row containing clip paths.
        transcriber: Active transcription backend.
        clip_cache: Transcript cache shared across items.

    Returns:
        A ``ClipTranscript`` bundle with both raw and hiragana forms.
    """

    word_text = cached_transcribe_file(item.get("word_clip_path"), transcriber, clip_cache)
    sentence_text = cached_transcribe_file(item.get("sentence_clip_path"), transcriber, clip_cache)
    return ClipTranscript(
        word_text=word_text,
        sentence_text=sentence_text,
        word_hira=phonetic_hiragana(word_text),
        sentence_hira=phonetic_hiragana(sentence_text),
    )


def cached_transcribe_file(
    clip_path: str | None,
    transcriber: TranscriptionBackend,
    clip_cache: dict[str, str],
) -> str:
    """Transcribe one clip path with memoization.

    Args:
        clip_path: Relative clip path from the manifest.
        transcriber: Active transcription backend.
        clip_cache: Transcript cache.

    Returns:
        The transcript text, or an empty string when the clip is missing.
    """

    if not clip_path:
        return ""
    cache_key = str(Path(clip_path))
    cached = clip_cache.get(cache_key)
    if cached is not None:
        return cached

    full_path = ROOT / clip_path
    if not full_path.exists():
        clip_cache[cache_key] = ""
        return ""

    text = transcribe_file(str(full_path), transcriber)
    clip_cache[cache_key] = text
    return text


def transcribe_file(
    audio_path: str,
    transcriber: TranscriptionBackend,
) -> str:
    """Transcribe one audio file through the configured backend.

    Args:
        audio_path: Path to the audio file.
        transcriber: Active transcription backend.

    Returns:
        The normalized transcript text.
    """

    if transcriber.kind == "whisper_cpp":
        return transcribe_file_with_whisper_cpp(audio_path, transcriber)
    result = transcriber.model.transcribe(audio_path, language="ja", fp16=False, temperature=0)
    return html.unescape(result.get("text", "")).strip()


def transcribe_file_with_whisper_cpp(
    audio_path: str,
    transcriber: TranscriptionBackend,
) -> str:
    """Transcribe one file using the Windows ``whisper.cpp`` CLI.

    Args:
        audio_path: Path to the source audio file.
        transcriber: Backend descriptor with CLI/model configuration.

    Returns:
        The combined transcript text extracted from the JSON output.

    Raises:
        RuntimeError: If the backend configuration is incomplete.
        FileNotFoundError: If the CLI binary or model file is missing.
    """

    if not transcriber.whisper_cpp_bin or not transcriber.whisper_cpp_model:
        raise RuntimeError("whisper.cpp backend requires WHISPER_CPP_BIN and WHISPER_CPP_MODEL")
    bin_path = Path(transcriber.whisper_cpp_bin)
    model_path = Path(transcriber.whisper_cpp_model)
    if not bin_path.exists():
        raise FileNotFoundError(f"whisper.cpp binary not found: {bin_path}")
    if not model_path.exists():
        raise FileNotFoundError(f"whisper.cpp model not found: {model_path}")

    audio_for_cli = audio_path
    temp_wav: str | None = None
    if not str(audio_path).lower().endswith(".wav"):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            temp_wav = tmp.name
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(audio_path),
                "-ac",
                "1",
                "-ar",
                "16000",
                temp_wav,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        audio_for_cli = temp_wav

    with tempfile.TemporaryDirectory() as tmpdir:
        output_base = str(Path(tmpdir) / "result")
        command = [
            str(bin_path),
            "-m",
            cli_path(str(model_path), bin_path),
            "-f",
            cli_path(audio_for_cli, bin_path),
            "-l",
            "ja",
            "-t",
            str(transcriber.whisper_cpp_threads),
            "-ojf",
            "-of",
            cli_path(output_base, bin_path),
            "-np",
        ]
        try:
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            output_json = Path(f"{output_base}.json")
            payload = json.loads(read_json_text(output_json))
            text = payload.get("transcription", [])
            if isinstance(text, list):
                combined = " ".join(part.get("text", "").strip() for part in text if isinstance(part, dict)).strip()
            else:
                combined = str(text).strip()
            return html.unescape(combined)
        finally:
            if temp_wav and os.path.exists(temp_wav):
                os.unlink(temp_wav)


def cli_path(path: str, bin_path: Path) -> str:
    """Return the path as-is (native Windows — no WSL conversion needed)."""
    return path


def read_json_text(path: Path) -> str:
    """Read a JSON file while tolerating Windows encoding edge cases.

    Args:
        path: JSON file written by a transcription backend.

    Returns:
        Decoded text suitable for ``json.loads``.
    """

    raw = path.read_bytes()
    # whisper.cpp's Windows JSON is mostly UTF-8, but token-level bytes can be
    # truncated inside the detailed token list. We only need the top-level JSON
    # structure plus the segment text, so a "replace" decode is the safest
    # recovery path: it preserves valid Japanese transcript text while keeping
    # the JSON itself parseable.
    #
    # We intentionally gate UTF-16 behind BOM/NUL-byte heuristics. Without that
    # guard, arbitrary single-byte output can be mis-decoded as UTF-16 and turn
    # perfectly usable JSON into gibberish.
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig", errors="replace")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")) or raw.count(b"\x00") > max(2, len(raw) // 8):
        for encoding in ("utf-16", "utf-16-le", "utf-16-be"):
            try:
                return raw.decode(encoding, errors="replace")
            except UnicodeDecodeError:
                continue

    for encoding in ("utf-8", "cp932", "shift_jis", "cp936", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue

    # Last resort for malformed-but-parseable JSON.
    return raw.decode("utf-8", errors="replace")


def similarity(left: str | None, right: str | None) -> float:
    """Compute fuzzy similarity between two normalized strings in [0.0, 1.0].

    Blends two signals:
    - SequenceMatcher ratio: general fuzzy similarity, handles insertions,
      deletions, and substitutions typical of ASR/OCR noise.
    - Containment bonus: len(shorter)/len(longer) when the shorter string is a
      substring of the longer. This handles the common case where a Whisper
      transcript includes the expected sentence plus some leading/trailing speech
      from an adjacent entry — raw SequenceMatcher would penalize the length
      difference even though the target text is cleanly present.

    The max() of the two means a clean substring match always wins over a noisy
    SequenceMatcher score, which is the right priority for short Japanese words
    inside longer compound transcripts.

    Args:
        left: First text (usually the expected/reference string).
        right: Second text (usually the ASR transcript).

    Returns:
        A score in ``[0.0, 1.0]``.
    """

    left_norm = normalize_text(left)
    right_norm = normalize_text(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0
    ratio = SequenceMatcher(None, left_norm, right_norm).ratio()
    shorter, longer = sorted((left_norm, right_norm), key=len)
    containment = len(shorter) / len(longer) if shorter in longer else 0.0
    return max(ratio, containment)


def boundary_similarity(expected: str | None, actual: str | None, side: str) -> float:
    """Compare only the beginning or ending portion of two strings.

    Args:
        expected: Expected text.
        actual: Candidate text.
        side: Either ``"start"`` or ``"end"``.

    Returns:
        Boundary-focused similarity in ``[0.0, 1.0]``.
    """

    expected_norm = normalize_text(expected)
    actual_norm = normalize_text(actual)
    if not expected_norm or not actual_norm:
        return 0.0
    expected_slice = slice_portion(expected_norm, side)
    actual_slice = slice_portion(actual_norm, side)
    return similarity(expected_slice, actual_slice)


def slice_portion(text: str, side: str) -> str:
    """Extract the start or end slice used for boundary comparison.

    Args:
        text: Already normalized text.
        side: Either ``"start"`` or ``"end"``.

    Returns:
        A representative slice from the requested side.
    """

    if not text:
        return ""
    # Focus on roughly the first/last third, but keep a reasonable minimum so
    # short sentences still provide usable evidence.
    width = max(4, len(text) // 3)
    if side == "start":
        return text[:width]
    return text[-width:]


def ratio_score(expected: str | None, actual: str | None) -> float:
    """Score whether two strings have compatible lengths.

    Args:
        expected: Expected text.
        actual: Candidate text.

    Returns:
        A value in ``[0.0, 1.0]`` that penalizes obviously missing content.
    """

    expected_norm = normalize_text(expected)
    actual_norm = normalize_text(actual)
    if not expected_norm or not actual_norm:
        return 0.0
    shorter = min(len(expected_norm), len(actual_norm))
    longer = max(len(expected_norm), len(actual_norm))
    ratio = shorter / longer
    if ratio >= 0.80:
        return 1.0
    if ratio >= 0.65:
        return (ratio - 0.65) / 0.15
    return 0.0


def split_transcript_parts(transcript: str, matching_mode: str | None) -> tuple[str, str]:
    """Split a merged transcript into word and sentence portions.

    Args:
        transcript: Stored transcript excerpt.
        matching_mode: Original matching mode from the manifest.

    Returns:
        A tuple of ``(word_part, sentence_part)``.
    """

    if not transcript:
        return "", ""
    if "/" in transcript:
        left, right = transcript.split("/", 1)
        return left.strip(), right.strip()
    if matching_mode == "split_segment":
        return transcript.strip(), ""
    return "", transcript.strip()


def phonetic_hiragana(text: str | None) -> str:
    """Convert Japanese text to a normalized hiragana reading via MeCab.

    This is the central normalization step that makes ASR output comparable to
    dictionary text. The problem it solves: the same word can appear as 「交流」
    in the vocabulary entry, 「こうりゅう」 in a Whisper transcript, or 「コウリュウ」
    in katakana from another ASR pass. All three should score ~1.0 against each
    other.

    MeCab (fugashi) provides the kana reading from its dictionary, which handles
    irregular readings and compound words that simple kana stripping would miss.
    jaconv.kata2hira normalizes katakana → hiragana because both ASR and
    dictionary output mix them freely. normalize_text then strips punctuation and
    whitespace so the downstream similarity functions see pure hiragana strings.

    Args:
        text: Surface text that may contain kanji, kana, or OCR noise.

    Returns:
        A hiragana-normalized string suitable for phonetic comparison.
    """

    if not text:
        return ""
    pieces: list[str] = []
    for token in tagger(str(text)):
        feature = token.feature
        kana = getattr(feature, "kana", None) or getattr(feature, "pron", None) or ""
        if kana and kana != "*":
            pieces.append(jaconv.kata2hira(kana))
        else:
            pieces.append(jaconv.kata2hira(token.surface))
    return normalize_text("".join(pieces))


def contains_normalized(container: str | None, target: str | None) -> bool:
    """Check normalized substring containment.

    Args:
        container: Larger text to search.
        target: Candidate substring to find.

    Returns:
        ``True`` when the normalized target occurs inside the normalized
        container.
    """

    # Exact substring hit after normalization is a surprisingly strong signal in
    # Japanese ASR cleanup, especially for readings like "ちょうなん".
    container_norm = normalize_text(container)
    target_norm = normalize_text(target)
    return bool(container_norm and target_norm and target_norm in container_norm)


def normalize_text(text: str | None) -> str:
    """Normalize text for deterministic fuzzy comparison.

    Args:
        text: Raw input text.

    Returns:
        Lowercased text with HTML entities, width variants, punctuation, and
        spacing normalized away.
    """

    # Normalize aggressively before any comparison:
    # - HTML entities
    # - full-width / half-width variants
    # - punctuation and spacing
    #
    # We do not perform deeper linguistic normalization here because we want to
    # keep the audit readable and deterministic.
    if not text:
        return ""
    normalized = html.unescape(str(text))
    normalized = unicodedata.normalize("NFKC", normalized)
    normalized = PUNCT_RE.sub("", normalized)
    return normalized.lower()


if __name__ == "__main__":
    main()
