#!/usr/bin/env python3
"""Re-audit cut vocabulary clips by re-transcribing the final MP3s.

This script is intentionally narrower than ``audit_review_candidates.py``:
it starts from an already-cut review JSON such as ``review_unit1_combined.json``
and answers two questions:

1. Does Whisper hear the clip as the expected word/sentence?
2. If not, what is the most likely reason?

Outputs:
    - ``*_clip_audit.json``: all rows with transcripts, scores, and diagnosis
    - ``*_clip_audit_suspect.json``: only suspect rows
    - ``*_clip_audit.md``: human-readable summary
    - ``*_clip_transcript_cache_<model>.json``: reusable clip transcript cache
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from audit_review_candidates import phonetic_hiragana, similarity, normalize_text
from align import load_backend, transcribe_full_track

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REVIEW_JSON = ROOT / "output" / "review_unit1_combined.json"
DEFAULT_OUTPUT_JSON = ROOT / "output" / "unit1_clip_audit.json"
DEFAULT_SUSPECT_JSON = ROOT / "output" / "unit1_clip_audit_suspect.json"
DEFAULT_OUTPUT_MD = ROOT / "output" / "unit1_clip_audit.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit already-cut unit clips with Whisper")
    parser.add_argument("--review-json", type=Path, default=DEFAULT_REVIEW_JSON)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--suspect-json", type=Path, default=DEFAULT_SUSPECT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--backend", choices=["openai", "whisper_cpp"], default="openai")
    parser.add_argument("--model", type=str, default="base", help="OpenAI Whisper model name")
    parser.add_argument("--device", type=str, default="cpu", help="Whisper device")
    parser.add_argument("--wcpp-binary", type=Path, default=None, help="Path to whisper-cli.exe")
    parser.add_argument("--wcpp-model", type=Path, default=None, help="Path to ggml model for whisper.cpp")
    parser.add_argument("--cache-json", type=Path, default=None, help="Optional transcript cache path")
    parser.add_argument("--unit", type=int, default=1, help="Unit number for report labelling only")
    return parser


def audio_duration(path: Path) -> float | None:
    if not path.exists():
        return None
    try:
        value = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            text=True,
        ).strip()
    except Exception:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_cache(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    return {str(k): str(v) for k, v in json.loads(path.read_text(encoding="utf-8")).items()}


def save_cache(path: Path | None, cache: dict[str, str]) -> None:
    if path is None:
        return
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def clip_cache_key(path: Path, cache_label: str) -> str:
    key_path = str(path.relative_to(ROOT)) if path.is_absolute() else str(path)
    if not path.exists():
        return f"{cache_label}:{key_path}:missing"
    stat = path.stat()
    # Include file identity so a recut clip at the same path does not reuse a stale transcript.
    return f"{cache_label}:{key_path}:{stat.st_size}:{stat.st_mtime_ns}"


def transcribe_clip(path: Path, backend: dict[str, Any], cache: dict[str, str], cache_label: str) -> str:
    key = clip_cache_key(path, cache_label)
    cached = cache.get(key)
    if cached is not None:
        return cached
    if not path.exists():
        cache[key] = ""
        return ""
    segments = transcribe_full_track(path, backend=backend)
    text = "".join(segment.get("text", "") for segment in segments).strip()
    cache[key] = text
    return text


def resolve_clip_path(value: str | None) -> Path | None:
    """Return an absolute clip path for a review-row field when present."""
    if not value:
        return None
    return ROOT / value.replace("\\", "/")


def edge_fragment_scores(actual_hira: str, expected_hira: str) -> tuple[float, float, float]:
    if not actual_hira or not expected_hira:
        return 0.0, 0.0, 0.0
    window = min(len(actual_hira), len(expected_hira))
    if window <= 0:
        return 0.0, 0.0, 0.0
    prefix_score = similarity(actual_hira, expected_hira[:window])
    suffix_score = similarity(actual_hira, expected_hira[-window:])
    coverage = window / max(1, len(expected_hira))
    return prefix_score, suffix_score, coverage


def build_track_index(review_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_track: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in review_rows:
        by_track[row["track_name"]].append(row)
    for rows in by_track.values():
        rows.sort(key=lambda item: item["index"])
    return by_track


def canonical_expected_sentence(text: str) -> str:
    """Drop non-spoken wrappers such as stage directions and outer quotes."""
    cleaned = text.strip()
    cleaned = re.sub(r"^\s*[\(（][^()（）]{1,20}[\)）]\s*", "", cleaned)
    if len(cleaned) >= 2 and cleaned[0] in "「『\"" and cleaned[-1] in "」』\"":
        cleaned = cleaned[1:-1].strip()
    return cleaned


def expected_sentence_candidates(text: str) -> list[str]:
    """Split a raw expected-sentence field into spoken candidate sentences."""
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


def note_sentence_fallback(note: str) -> str:
    cleaned = (note or "").strip()
    if not cleaned.startswith("sentence:"):
        return ""
    body = cleaned.split(":", 1)[1].strip()
    body = re.sub(r"\s*\([^)]*\)\s*$", "", body).strip()
    return canonical_expected_sentence(body)


def row_sentence_candidates(row: dict[str, Any]) -> list[str]:
    expected = expected_sentence_candidates(row.get("expected_sentence") or "")
    if expected:
        return expected
    fallback = note_sentence_fallback(row.get("note", ""))
    return [fallback] if fallback else []


def best_expected_sentence(row: dict[str, Any], transcript_text: str = "") -> tuple[str, list[str], float]:
    candidates = row_sentence_candidates(row)
    if not candidates:
        return "", [], 0.0
    if not transcript_text:
        return candidates[0], candidates, 0.0

    transcript_hira = phonetic_hiragana(transcript_text)
    best_candidate = candidates[0]
    best_score = similarity(transcript_hira, phonetic_hiragana(best_candidate))
    for candidate in candidates[1:]:
        score = similarity(transcript_hira, phonetic_hiragana(candidate))
        if score > best_score:
            best_candidate = candidate
            best_score = score
    return best_candidate, candidates, best_score


def best_neighbor_match(
    transcript_hira: str,
    own_index: int,
    candidates: list[dict[str, Any]],
    field: str,
) -> tuple[int | None, float]:
    best_index = None
    best_score = -1.0
    for item in candidates:
        if field == "expected_sentence":
            expected_options = row_sentence_candidates(item)
            if not expected_options:
                continue
            score = max(similarity(transcript_hira, phonetic_hiragana(expected)) for expected in expected_options)
        else:
            expected = item[field]
            score = similarity(transcript_hira, phonetic_hiragana(expected))
        if score > best_score:
            best_index = item["index"]
            best_score = score
    return best_index, best_score


def diagnose_word(
    row: dict[str, Any],
    word_text: str,
    track_rows: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    expected_word = row.get("reading") or row.get("headword") or ""
    expected_sentence = row.get("expected_sentence") or ""
    word_hira = phonetic_hiragana(word_text)
    own_word_score = similarity(word_hira, phonetic_hiragana(expected_word))
    own_sentence_score = similarity(word_hira, phonetic_hiragana(expected_sentence))
    best_idx, best_score = best_neighbor_match(word_hira, row["index"], track_rows, "reading")
    reasons: list[str] = []

    if not word_text:
        reasons.append("word_transcript_empty")
    if own_sentence_score >= own_word_score + 0.12:
        reasons.append("word_clip_contains_sentence_audio")
    if best_idx is not None and best_idx != row["index"] and best_score >= own_word_score + 0.12:
        reasons.append(f"word_matches_neighbor_{best_idx}")
    if normalize_text(word_text) and len(normalize_text(word_text)) >= max(6, 2 * len(normalize_text(expected_word))):
        reasons.append("word_clip_too_long_or_merged")
    if own_word_score < 0.45 and not reasons:
        reasons.append("word_asr_mismatch")

    if not reasons:
        if own_word_score >= 0.72:
            return "ok", []
        if own_word_score >= 0.45:
            return "asr_noise", ["word_orthography_or_reading_drift"]
        return "suspect", ["word_low_similarity"]
    if reasons == ["word_orthography_or_reading_drift"]:
        return "asr_noise", reasons
    return "suspect", reasons


def diagnose_sentence(
    row: dict[str, Any],
    sentence_text: str,
    track_rows: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    expected_word = row.get("reading") or row.get("headword") or ""
    expected_sentence, _, own_sentence_score = best_expected_sentence(row, sentence_text)
    sentence_hira = phonetic_hiragana(sentence_text)
    expected_sentence_hira = phonetic_hiragana(expected_sentence)
    own_word_score = similarity(sentence_hira, phonetic_hiragana(expected_word))
    best_idx, best_score = best_neighbor_match(sentence_hira, row["index"], track_rows, "expected_sentence")
    reasons: list[str] = []
    prefix_score, suffix_score, coverage_ratio = edge_fragment_scores(sentence_hira, expected_sentence_hira)

    if not sentence_text:
        reasons.append("sentence_transcript_empty")
    if own_word_score >= own_sentence_score + 0.10:
        reasons.append("sentence_clip_contains_only_word")
    if best_idx is not None and best_idx != row["index"] and best_score >= own_sentence_score + 0.12:
        reasons.append(f"sentence_matches_neighbor_{best_idx}")
    if coverage_ratio and coverage_ratio < 0.80 and max(prefix_score, suffix_score) >= 0.90:
        reasons.append("sentence_prefix_or_suffix_only")
    if normalize_text(sentence_text):
        expected_len = len(normalize_text(expected_sentence))
        actual_len = len(normalize_text(sentence_text))
        if expected_len and actual_len / expected_len < 0.45:
            reasons.append("sentence_clip_truncated")
    if own_sentence_score < 0.55 and not reasons:
        reasons.append("sentence_asr_mismatch")

    if not reasons:
        if own_sentence_score >= 0.72:
            return "ok", []
        if own_sentence_score >= 0.55:
            return "asr_noise", ["sentence_orthography_or_reading_drift"]
        return "suspect", ["sentence_low_similarity"]
    if reasons == ["sentence_orthography_or_reading_drift"]:
        return "asr_noise", reasons
    return "suspect", reasons


def summarize_overall(word_status: str, sentence_status: str) -> str:
    if "suspect" in (word_status, sentence_status):
        return "suspect"
    if "asr_noise" in (word_status, sentence_status):
        return "asr_noise"
    return "ok"


def add_micro_region_word_hint(
    row: dict[str, Any],
    word_text: str,
    word_duration: float | None,
    sentence_score: float,
    word_status: str,
    word_reasons: list[str],
) -> tuple[str, list[str]]:
    expected_word = phonetic_hiragana(row.get("reading") or row.get("headword") or "")
    actual_word = phonetic_hiragana(word_text)
    if not expected_word or word_status == "ok":
        return word_status, word_reasons

    trailing_scores = [
        similarity(actual_word, expected_word[drop:])
        for drop in (1, 2)
        if len(expected_word) > drop
    ]
    best_trailing_score = max(trailing_scores, default=0.0)
    short_clip = (word_duration or 0.0) <= 0.55
    long_expected = len(expected_word) >= 4

    if sentence_score >= 0.85 and short_clip and long_expected:
        if best_trailing_score >= 0.75 or not actual_word:
            if "word_possible_micro_region_lead_in" not in word_reasons:
                word_reasons = list(word_reasons) + ["word_possible_micro_region_lead_in"]
            word_status = "suspect"
    return word_status, word_reasons


def main() -> None:
    args = build_parser().parse_args()
    review_rows = json.loads(args.review_json.read_text(encoding="utf-8"))
    track_rows = build_track_index(review_rows)
    backend = load_backend(
        args.backend,
        model_name=args.model,
        device=args.device,
        wcpp_binary=args.wcpp_binary,
        wcpp_model=args.wcpp_model,
    )
    cache_label = backend_cache_label(args, backend)
    cache_path = args.cache_json or (ROOT / "output" / f"unit{args.unit:02d}_clip_transcript_cache_{cache_label}.json")
    cache = load_cache(cache_path)

    audited: list[dict[str, Any]] = []
    suspects: list[dict[str, Any]] = []

    for row in review_rows:
        word_path = resolve_clip_path(row.get("word_clip"))
        sentence_path = resolve_clip_path(row.get("sentence_clip"))
        word_duration = audio_duration(word_path) if word_path else None
        sentence_duration = audio_duration(sentence_path) if sentence_path else None
        word_text = transcribe_clip(word_path, backend, cache, cache_label) if word_path else ""
        sentence_text = transcribe_clip(sentence_path, backend, cache, cache_label) if sentence_path else ""

        expected_word = row.get("reading") or row.get("headword") or ""
        expected_sentence, sentence_candidates, sentence_score_raw = best_expected_sentence(row, sentence_text)
        word_hira = phonetic_hiragana(word_text)
        sentence_hira = phonetic_hiragana(sentence_text)

        word_score = round(similarity(word_hira, phonetic_hiragana(expected_word)), 3)
        sentence_score = round(sentence_score_raw, 3)
        neighbors = track_rows.get(row.get("track_name", ""), [])
        word_status, word_reasons = diagnose_word(row, word_text, neighbors)
        sentence_status, sentence_reasons = diagnose_sentence(row, sentence_text, neighbors)
        word_status, word_reasons = add_micro_region_word_hint(
            row,
            word_text,
            word_duration,
            sentence_score,
            word_status,
            word_reasons,
        )
        overall = summarize_overall(word_status, sentence_status)

        audit_row = {
            "index": row["index"],
            "unit_number": row.get("unit_number"),
            "track_name": row["track_name"],
            "headword": row.get("headword"),
            "reading": row.get("reading"),
            "expected_sentence_raw": row.get("expected_sentence"),
            "expected_sentence": expected_sentence,
            "expected_sentence_candidates": sentence_candidates,
            "word_clip": row.get("word_clip"),
            "sentence_clip": row.get("sentence_clip"),
            "word_duration": word_duration,
            "sentence_duration": sentence_duration,
            "word_transcript_audit": word_text,
            "sentence_transcript_audit": sentence_text,
            "word_score_audit": word_score,
            "sentence_score_audit": sentence_score,
            "word_status": word_status,
            "sentence_status": sentence_status,
            "status": overall,
            "word_reasons": word_reasons,
            "sentence_reasons": sentence_reasons,
            "note": row.get("note", ""),
        }
        audited.append(audit_row)
        if overall == "suspect":
            suspects.append(audit_row)

    args.output_json.write_text(json.dumps(audited, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.suspect_json.write_text(json.dumps(suspects, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    save_cache(cache_path, cache)

    by_status: dict[str, int] = defaultdict(int)
    for row in audited:
        by_status[row["status"]] += 1

    lines = [
        f"# Unit {args.unit} clip audit",
        "",
        f"- Review source: `{display_path(args.review_json)}`",
        f"- Backend: `{cache_label}`",
        f"- Total rows: `{len(audited)}`",
        f"- OK: `{by_status.get('ok', 0)}`",
        f"- ASR noise only: `{by_status.get('asr_noise', 0)}`",
        f"- Suspect: `{by_status.get('suspect', 0)}`",
        "",
        "## Suspects",
        "",
    ]

    for row in suspects:
        reason_text = ", ".join(row["word_reasons"] + row["sentence_reasons"]) or "none"
        lines.extend(
            [
                f"### {row['index']} {row['headword']} ({row['track_name']})",
                "",
                f"- Expected sentence: `{row['expected_sentence']}`",
                f"- Word: `{row['word_transcript_audit']}` | score `{row['word_score_audit']}` | status `{row['word_status']}`",
                f"- Sentence: `{row['sentence_transcript_audit']}` | score `{row['sentence_score_audit']}` | status `{row['sentence_status']}`",
                f"- Reason(s): {reason_text}",
                f"- Existing note: {row['note'] or 'none'}",
                "",
            ]
        )

    args.output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "rows": len(audited),
                "ok": by_status.get("ok", 0),
                "asr_noise": by_status.get("asr_noise", 0),
                "suspect": by_status.get("suspect", 0),
                "backend": cache_label,
                "output_json": display_path(args.output_json),
                "suspect_json": display_path(args.suspect_json),
                "output_md": display_path(args.output_md),
                "cache_json": display_path(cache_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
