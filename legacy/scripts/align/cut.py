"""Audio clip cutting and post-cut rescoring.

`cut_clip` is a thin ffmpeg wrapper used everywhere clips are produced.
`rescore_clip` re-transcribes a finished clip to fill word_score/sentence_score
with an objective quality signal for reviewers.
`cut_clips_from_mapping` is the execution phase of the pipeline: it consumes
an LLM mapping, resolves boundaries, and calls ffmpeg for every entry.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from align._constants import ROOT
from align.backend import _transcribe_wcpp
from align.boundaries import (
    normalize_flag_list,
    resolve_cut_span,
    summarize_piece_coverage,
    log_boundary_decision,
)
from align.silence import enumerate_speech_pieces
from align.text import kana_similarity


def cut_clip(source: Path, dest: Path, start: float, end: float) -> bool:
    """Extract a time slice from source and write as MP3 at dest.

    Uses libmp3lame at quality 2 (near-transparent). Returns True when the
    dest file was created successfully.
    """
    duration = end - start
    if duration <= 0.0:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{start:.3f}", "-t", f"{duration:.3f}",
        "-i", str(source),
        "-acodec", "libmp3lame", "-q:a", "2",
        str(dest),
    ]
    subprocess.run(cmd, check=False)
    return dest.exists()


def rescore_clip(
    clip_path: Path,
    expected: str,
    backend,
) -> tuple[str | None, float | None]:
    """Re-transcribe a cut clip and score it against `expected` via kana similarity.

    `backend` is either a dict handle from `load_backend()` or, for backward
    compatibility, a raw Python-whisper model object.

    Returns (transcript, score). Transcript is `None` if Whisper produced no
    text. Score is `None` only when we couldn't even attempt the comparison.

    Post-cut rescoring exists because the LLM mapping and silence snapping can
    still produce a slightly wrong boundary — especially when two vocab entries
    share a piece boundary. The rescore fills word_score / sentence_score with
    an objective quality signal so the audit step and human reviewers can
    immediately spot clips that Whisper itself doesn't recognize.
    """
    if not clip_path.exists():
        return None, None

    if isinstance(backend, dict):
        kind = backend["kind"]
    else:
        kind, backend = "openai", {"kind": "openai", "model": backend}

    try:
        if kind == "openai":
            result = backend["model"].transcribe(str(clip_path), language="ja", verbose=False)
            transcript = (result.get("text") or "").strip() or None
        else:
            segs = _transcribe_wcpp(clip_path, backend["binary"], backend["model_bin"])
            transcript = " ".join(s["text"] for s in segs).strip() or None
    except Exception as exc:  # noqa: BLE001
        print(f"  [WARN] rescore failed for {clip_path.name}: {exc}", file=sys.stderr, flush=True)
        return None, None

    score = kana_similarity(transcript or "", expected) if transcript else 0.0
    return transcript, score


def cut_clips_from_mapping(
    track_path: Path,
    mapping: list[dict],
    entries: list[dict],
    boundaries: list[tuple],
    segments: list[dict],
    unit_num: int,
    dry_run: bool = False,
    output: str = "output/review_assigned_llm.json",
    rescore_model=None,
) -> list[dict]:
    """Cut audio clips from a track based on an LLM-produced mapping.

    This is the execution phase: the LLM has told us which piece_ids belong to
    which word/sentence clip; now we resolve exact cut boundaries and invoke
    ffmpeg. The result JSON is the input to merge_assigned_clips.py.

    The full_track `segments` are used only to fill word_transcript for display —
    they are not used for boundary decisions. All boundary decisions go through
    resolve_cut_span → silence snapping.

    Args:
        track_path: Path to the source audio file.
        mapping: LLM output — list of {index, word?, sentence?, flags?, note?}.
        entries: Vocabulary entry dicts for this track.
        boundaries: Silence boundaries from detect_silence_boundaries().
        segments: Whisper segments from transcribe_full_track() (display only).
        unit_num: Unit number for output directory naming.
        dry_run: Validate and log the mapping but skip all ffmpeg calls.
        output: Output JSON path relative to ROOT.
        rescore_model: Backend handle for post-cut clip rescoring, or None.

    Returns:
        List of alignment records compatible with merge_assigned_clips.py.
    """
    clips_dir = ROOT / "output" / "clips" / f"unit{unit_num:02d}"
    clips_dir.mkdir(parents=True, exist_ok=True)

    track_rel = str(track_path.relative_to(ROOT))
    pieces = enumerate_speech_pieces(boundaries, max((t for t, _ in boundaries), default=0.0))
    missing_pieces, invalid_piece_ids, duplicate_piece_ids = summarize_piece_coverage(mapping, pieces)
    if missing_pieces:
        print(f"  [WARN] mapping leaves speech pieces unassigned: {missing_pieces}", file=sys.stderr, flush=True)
    if invalid_piece_ids:
        print(f"  [WARN] mapping references invalid speech piece ids: {invalid_piece_ids}", file=sys.stderr, flush=True)
    if duplicate_piece_ids:
        print(f"  [WARN] mapping reuses speech pieces across clips: {duplicate_piece_ids}", file=sys.stderr, flush=True)

    results = []
    for item in mapping:
        idx = item["index"]
        entry_data = next((e for e in entries if e["index"] == idx), None)
        if entry_data is None:
            print(f"  [WARN] Index {idx} not in entries, skipping", flush=True)
            continue

        item_flags = normalize_flag_list(item.get("flags"))
        result = {
            "index": idx,
            "unit_number": unit_num,
            "headword": entry_data["headword"],
            "reading": entry_data.get("reading", ""),
            "expected_sentence": entry_data.get("sentence", ""),
            "track_name": track_path.name,
            "track_path": track_rel,
            "word_clip": None,
            "sentence_clip": None,
            "word_start": None,
            "word_end": None,
            "sentence_start": None,
            "sentence_end": None,
            "word_transcript": None,
            "sentence_transcript": None,
            "word_score": None,
            "sentence_score": None,
            "match_method": "llm_whisper_silence",
            "whisper_confidence": None,
            "chunk_count": 0,
            "note": item.get("note", ""),
            "flags": item_flags,
            "word_flags": [],
            "sentence_flags": [],
            "word_piece_ids": [],
            "sentence_piece_ids": [],
            "word_boundary_policy": {},
            "sentence_boundary_policy": {},
        }

        if "word" in item:
            w = item["word"]
            word_local_flags = normalize_flag_list(w.get("flags"))
            word_flags = word_local_flags + item_flags
            preserve = set(normalize_flag_list(w.get("preserve_boundaries")))
            if "bridge_split" in word_local_flags and not preserve:
                preserve = {"start", "end"}
            ws, we, word_policies, word_deltas = resolve_cut_span(
                w["start"], w["end"], boundaries, preserve_boundaries=preserve,
            )
            log_boundary_decision("word", idx, word_policies, word_deltas)
            seg = next((s for s in segments if s["start"] <= w["start"] <= s["end"]), None)
            if seg:
                result["word_transcript"] = seg["text"]
            result["word_flags"] = sorted(set(word_flags + [
                p for p in word_policies.values() if p != "silence_snap"
            ]))
            result["word_piece_ids"] = w.get("piece_ids") or []
            result["word_boundary_policy"] = word_policies
            if not dry_run:
                dest = clips_dir / f"word{idx}.mp3"
                if cut_clip(track_path, dest, ws, we):
                    result["word_clip"] = str(dest.relative_to(ROOT))
                    result["word_start"] = ws
                    result["word_end"] = we

        if "sentence" in item:
            s = item["sentence"]
            sentence_local_flags = normalize_flag_list(s.get("flags"))
            sentence_flags = sentence_local_flags + item_flags
            preserve = set(normalize_flag_list(s.get("preserve_boundaries")))
            if "bridge_split" in sentence_local_flags and not preserve:
                preserve = {"start", "end"}
            ss, se, sentence_policies, sentence_deltas = resolve_cut_span(
                s["start"], s["end"], boundaries, preserve_boundaries=preserve,
            )
            log_boundary_decision("sentence", idx, sentence_policies, sentence_deltas)
            texts = [
                seg["text"] for seg in segments
                if seg["start"] >= s["start"] - 0.1 and seg["end"] <= s["end"] + 0.1
            ]
            result["sentence_transcript"] = " ".join(texts) if texts else None
            result["sentence_flags"] = sorted(set(sentence_flags + [
                p for p in sentence_policies.values() if p != "silence_snap"
            ]))
            result["sentence_piece_ids"] = s.get("piece_ids") or []
            result["sentence_boundary_policy"] = sentence_policies
            if not dry_run:
                dest = clips_dir / f"sentence{idx}.mp3"
                if cut_clip(track_path, dest, ss, se):
                    result["sentence_clip"] = str(dest.relative_to(ROOT))
                    result["sentence_start"] = ss
                    result["sentence_end"] = se

        result["flags"] = sorted(set(
            result["flags"] + result["word_flags"] + result["sentence_flags"]
        ))

        # Post-cut re-transcription scoring: fills word_score / sentence_score
        # with an objective quality signal so auditors can spot bad clips fast.
        if rescore_model is not None and not dry_run:
            if result["word_clip"]:
                clip_path = ROOT / result["word_clip"]
                expected_word = entry_data.get("reading") or entry_data.get("headword", "")
                transcript, score = rescore_clip(clip_path, expected_word, rescore_model)
                if transcript is not None:
                    result["word_transcript"] = transcript
                if score is not None:
                    result["word_score"] = round(score, 3)
            if result["sentence_clip"]:
                clip_path = ROOT / result["sentence_clip"]
                transcript, score = rescore_clip(clip_path, entry_data.get("sentence", ""), rescore_model)
                if transcript is not None:
                    result["sentence_transcript"] = transcript
                if score is not None:
                    result["sentence_score"] = round(score, 3)

        results.append(result)

    if not dry_run:
        out_path = ROOT / output
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nWrote {len(results)} records to {out_path}", flush=True)
        print(f"Run: python parse/scripts/merge_assigned_clips.py {output}", flush=True)

    return results
