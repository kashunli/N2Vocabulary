#!/usr/bin/env python3
"""CLI entry point — align one audio track to vocabulary entries.

## What this script does

Given an MP3 track and a JSON list of vocabulary entries, it:
  1. Transcribes the track with Whisper (full-track + per-silence-piece).
  2. Builds a structured prompt listing all speech pieces with timestamps.
  3. Sends/prints that prompt for an LLM (Claude) to produce a JSON mapping
     of piece_ids → word/sentence clip boundaries.
  4. Snaps each LLM timestamp to the nearest real silence edge and cuts the
     final MP3 clips with ffmpeg.

Two prompt-generation modes are supported:
  - exact-window: the entries file is the exact track range
  - unit-sequential: the entries file is a larger candidate list and the track
    starts at a known index that GPT must extend to the true end

All business logic lives in the `align/` package. This file is intentionally
thin so an AI agent can read it and understand the full CLI surface in one pass.

## Quick reference

    # Typical run: generate prompt, paste to Claude, cut clips
    python parse/scripts/align_track_by_llm.py \\
        --backend whisper_cpp \\
        --wcpp-binary tools/whispercpp-windows/whisper-cli.exe \\
        --wcpp-model  tools/whispercpp-windows/ggml-large-v3-turbo.bin \\
        --track "audio/Unit5 形容詞A/34 5-34.mp3" \\
        --entries-json output/unit5_entries/entries_34.json \\
        --unit 5 \\
        --save-wcpp-cache

    # Sequential prompt generation from a larger candidate file
    python parse/scripts/align_track_by_llm.py \\
        --backend whisper_cpp \\
        --wcpp-binary tools/whispercpp-windows/whisper-cli.exe \\
        --wcpp-model  tools/whispercpp-windows/ggml-large-v3-turbo.bin \\
        --track "audio/Unit6 副詞A＋接続詞/39 1-39.mp3" \\
        --entries-json output/unit6_entries/unit6_511_580.json \\
        --mapping-mode unit-sequential \\
        --current-track-start-index 511 \\
        --prompt-only

    # Non-interactive: supply the LLM JSON response directly
    python parse/scripts/align_track_by_llm.py \\
        --track ... --entries-json ... --unit 5 \\
        --llm-json output/unit5_mappings/mapping_34.json

    # Smoke-test the backend config
    python parse/scripts/align_track_by_llm.py \\
        --backend whisper_cpp \\
        --wcpp-binary tools/whispercpp-windows/whisper-cli.exe \\
        --wcpp-model  tools/whispercpp-windows/ggml-large-v3-turbo.bin \\
        --backend-info

## Output

    output/review_assigned_llm.json   — alignment records (merge with merge_assigned_clips.py)
    output/clips/unitXX/word{N}.mp3   — word pronunciation clips
    output/clips/unitXX/sentence{N}.mp3 — example sentence clips
    output/whisper_cache/             — Whisper transcript + silence boundary sidecars
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from align import (
    ROOT,
    build_prompt,
    cut_clips_from_mapping,
    default_prompt_support_prefix,
    default_wcpp_cache_prefix,
    detect_silence_boundaries,
    display_path,
    enumerate_speech_pieces,
    load_backend,
    speech_regions,
    transcribe_full_track,
    transcribe_speech_pieces,
    write_silence_boundary_artifact,
    write_wcpp_cache_artifacts,
)


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Align one audio track to vocabulary entries via Whisper + LLM.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # --- required inputs (unless --backend-info) ---
    ap.add_argument(
        "--track", type=str, help="Path to audio track (relative to project root)."
    )
    ap.add_argument(
        "--entries-json",
        type=str,
        help="JSON file with vocabulary entries. Exact track list in exact-window mode, larger candidate list in unit-sequential mode.",
    )

    # --- output ---
    ap.add_argument(
        "--output",
        type=str,
        default="output/review_assigned_llm.json",
        help="Output JSON path (relative to project root).",
    )
    ap.add_argument(
        "--unit",
        type=int,
        help="Unit number — used to name the output clips directory.",
    )
    ap.add_argument(
        "--mapping-mode",
        choices=["exact-window", "unit-sequential"],
        default="exact-window",
        help="Prompt/mapping mode. exact-window expects an exact track range; unit-sequential expects a larger candidate list with a known start index.",
    )
    ap.add_argument(
        "--current-track-start-index",
        type=int,
        help="Known first index for this track in unit-sequential mode.",
    )

    # --- backend ---
    ap.add_argument(
        "--backend",
        choices=["openai", "whisper_cpp"],
        default="whisper_cpp",
        help="Transcription backend. 'whisper_cpp' uses Vulkan GPU on AMD.",
    )
    ap.add_argument(
        "--model",
        type=str,
        default="base",
        help="OpenAI Whisper model name (openai backend only).",
    )
    ap.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="'cpu' or 'cuda' (openai backend only).",
    )
    ap.add_argument(
        "--wcpp-binary",
        type=str,
        default=None,
        help="Path to whisper-cli.exe. Defaults to env WHISPER_CPP_BIN.",
    )
    ap.add_argument(
        "--wcpp-model",
        type=str,
        default=None,
        help="Path to ggml-*.bin model. Defaults to env WHISPER_CPP_MODEL.",
    )
    ap.add_argument(
        "--backend-info",
        action="store_true",
        help="Print resolved backend config and exit (smoke test).",
    )

    # --- silence detection ---
    ap.add_argument(
        "--silence-noise",
        type=str,
        default="-32dB",
        help="Noise floor for ffmpeg silencedetect (default -32dB).",
    )
    ap.add_argument(
        "--silence-duration",
        type=float,
        default=0.25,
        help="Min silence duration in seconds (default 0.25; use 0.18 for dense audio).",
    )

    # --- cache ---
    ap.add_argument(
        "--save-wcpp-cache",
        action="store_true",
        help="Persist Whisper transcript artifacts under --wcpp-cache-dir.",
    )
    ap.add_argument(
        "--wcpp-cache-dir",
        type=str,
        default="output/whisper_cache",
        help="Directory for Whisper cache artifacts.",
    )

    # --- operating modes ---
    ap.add_argument(
        "--prompt-only",
        action="store_true",
        help="Print the LLM prompt and exit without waiting for a response.",
    )
    ap.add_argument(
        "--llm-json",
        type=str,
        help="Path to a pre-computed LLM mapping JSON (non-interactive mode).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the mapping but skip all ffmpeg clip-cutting calls.",
    )
    ap.add_argument(
        "--rescore",
        action="store_true",
        help="Re-transcribe each cut clip and fill word_score/sentence_score.",
    )

    return ap


def _resolve_input_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def _normalize_mapping_indices(mapping: list[dict]) -> list[int]:
    indices: list[int] = []
    for item in mapping:
        try:
            indices.append(int(item["index"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Mapping item has invalid index: {item!r}") from exc
    return indices


def _validate_entries(
    entries: list[dict],
    mapping_mode: str,
    current_track_start_index: int | None,
) -> None:
    if not isinstance(entries, list) or not entries:
        raise ValueError("entries-json must contain a non-empty JSON array")

    seen: set[int] = set()
    previous: int | None = None
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("entries-json must contain objects")
        try:
            index = int(entry["index"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Entry has invalid index: {entry!r}") from exc
        if previous is not None and index <= previous:
            raise ValueError("entries-json must be sorted by strictly increasing index")
        if index in seen:
            raise ValueError(f"entries-json contains duplicate index {index}")
        seen.add(index)
        previous = index

    if mapping_mode == "unit-sequential":
        if current_track_start_index is None:
            raise ValueError("--current-track-start-index is required in unit-sequential mode")
        if current_track_start_index not in seen:
            raise ValueError(
                f"current track start index {current_track_start_index} is not present in entries-json"
            )


def _validate_unit_sequential_mapping(
    mapping: list[dict],
    entries: list[dict],
    current_track_start_index: int,
) -> tuple[int, int]:
    if not mapping:
        raise ValueError("unit-sequential mapping cannot be empty")
    mapping_indices = _normalize_mapping_indices(mapping)
    if mapping_indices[0] != current_track_start_index:
        raise ValueError(
            f"unit-sequential mapping must start at index {current_track_start_index}, "
            f"but got {mapping_indices[0]}"
        )
    for left, right in zip(mapping_indices, mapping_indices[1:]):
        if right != left + 1:
            raise ValueError(
                f"unit-sequential mapping indices must be contiguous; found gap {left} -> {right}"
            )
    valid_indices = {int(entry["index"]) for entry in entries}
    invalid = [idx for idx in mapping_indices if idx not in valid_indices]
    if invalid:
        raise ValueError(
            "unit-sequential mapping references indices not present in entries-json: "
            f"{invalid}"
        )
    return mapping_indices[0], mapping_indices[-1]


def _report_sequential_boundary(first_index: int, last_index: int) -> None:
    print(
        f"Sequential mapping range: {first_index}-{last_index}",
        flush=True,
    )
    print(
        f"Suggested next track start: {last_index + 1}",
        flush=True,
    )


def main() -> None:
    args = _build_parser().parse_args()

    backend = load_backend(
        args.backend,
        model_name=args.model,
        device=args.device,
        wcpp_binary=args.wcpp_binary,
        wcpp_model=args.wcpp_model,
    )

    if args.backend_info:
        if backend["kind"] == "openai":
            print(f"Backend: openai whisper | model={args.model} device={args.device}")
        else:
            print(f"Backend: whisper.cpp")
            print(f"  binary: {backend['binary']}")
            print(f"  model : {backend['model_bin']}")
        return

    if not args.track or not args.entries_json:
        _build_parser().error(
            "--track and --entries-json are required (unless --backend-info)"
        )

    track_path = ROOT / args.track
    entries_path = _resolve_input_path(args.entries_json)
    entries = json.loads(entries_path.read_text(encoding="utf-8"))
    _validate_entries(entries, args.mapping_mode, args.current_track_start_index)
    unit_num = args.unit or entries[0].get("unit_number", 1)

    save_cache = args.save_wcpp_cache and backend["kind"] == "whisper_cpp"
    cache_dir = (ROOT / args.wcpp_cache_dir) if save_cache else None
    cache_prefix = (
        default_wcpp_cache_prefix(track_path, unit_num, backend["model_bin"])
        if save_cache
        else None
    )
    rescore_backend = backend if args.rescore else None

    print(f"Track: {track_path.name}", flush=True)
    print(
        f"Entries: {len(entries)} (indices {entries[0]['index']}-{entries[-1]['index']})",
        flush=True,
    )
    print(f"Mapping mode: {args.mapping_mode}", flush=True)
    if args.mapping_mode == "unit-sequential":
        print(
            f"Current track start index: {args.current_track_start_index}",
            flush=True,
        )
    if save_cache:
        print(f"Cache dir: {display_path(ROOT / args.wcpp_cache_dir)}", flush=True)

    # -----------------------------------------------------------------------
    # Non-interactive mode: LLM mapping already on disk, just cut.
    # -----------------------------------------------------------------------
    if args.llm_json:
        print("\n[1/3] Transcribing track...", flush=True)
        segments = transcribe_full_track(
            track_path, backend=backend, cache_dir=cache_dir, cache_prefix=cache_prefix
        )
        print(f"  {len(segments)} segments", flush=True)

        print("\n[2/3] Detecting silence boundaries...", flush=True)
        boundaries, _ = detect_silence_boundaries(
            track_path, args.silence_noise, args.silence_duration
        )
        print(f"  {len(boundaries)} boundaries", flush=True)

        print("\n[3/3] Cutting clips from LLM mapping...", flush=True)
        mapping = json.loads(Path(args.llm_json).read_text(encoding="utf-8"))
        if args.mapping_mode == "unit-sequential":
            first_index, last_index = _validate_unit_sequential_mapping(
                mapping, entries, args.current_track_start_index
            )
            _report_sequential_boundary(first_index, last_index)
        cut_clips_from_mapping(
            track_path,
            mapping,
            entries,
            boundaries,
            segments,
            unit_num,
            dry_run=args.dry_run,
            output=args.output,
            rescore_model=rescore_backend,
        )
        return

    # -----------------------------------------------------------------------
    # Interactive / prompt-only mode: run all stages, print prompt.
    # -----------------------------------------------------------------------
    print("\n[1/5] Transcribing track...", flush=True)
    segments = transcribe_full_track(
        track_path, backend=backend, cache_dir=cache_dir, cache_prefix=cache_prefix
    )
    print(f"  {len(segments)} segments", flush=True)

    print("\n[2/5] Detecting silence boundaries...", flush=True)
    boundaries, duration = detect_silence_boundaries(
        track_path, args.silence_noise, args.silence_duration
    )
    regions = speech_regions(boundaries, duration)
    print(
        f"  {len(regions)} speech regions, {len(boundaries)} silence boundaries",
        flush=True,
    )

    print("\n[3/5] Transcribing speech pieces...", flush=True)
    pieces = enumerate_speech_pieces(boundaries, duration)
    piece_transcripts, piece_cache_path = transcribe_speech_pieces(
        track_path,
        pieces,
        backend=backend,
        silence_noise=args.silence_noise,
        silence_duration=args.silence_duration,
        cache_dir=cache_dir,
        cache_prefix=cache_prefix,
    )
    print(f"  {len(piece_transcripts)} pieces transcribed", flush=True)
    if piece_cache_path:
        print(f"  Piece cache: {display_path(piece_cache_path)}", flush=True)

    support_dir = cache_dir or (ROOT / "output" / "whisper_cache")
    support_prefix = cache_prefix or default_prompt_support_prefix(
        track_path, unit_num, backend
    )
    write_wcpp_cache_artifacts(support_dir, support_prefix, segments)
    full_track_ref = display_path(support_dir / f"{support_prefix}_segments.json")
    silence_ref = display_path(
        write_silence_boundary_artifact(
            support_dir, support_prefix, boundaries, duration
        )
    )
    print(f"  Sidecars: {full_track_ref} | {silence_ref}", flush=True)

    print("\n[4/5] Building LLM prompt...", flush=True)
    prompt = build_prompt(
        track_path,
        segments,
        regions,
        entries,
        boundaries,
        duration,
        piece_transcripts,
        full_track_segments_ref=full_track_ref,
        silence_boundaries_ref=silence_ref,
        mapping_mode=args.mapping_mode,
        entries_ref=display_path(entries_path),
        current_track_start_index=args.current_track_start_index,
    )

    print("\n" + "=" * 80)
    print(prompt)
    print("=" * 80)

    if args.prompt_only:
        return

    # -----------------------------------------------------------------------
    # Step 5: wait for the user to paste the LLM JSON mapping back.
    # -----------------------------------------------------------------------
    print()
    print("[5/5] Paste the JSON mapping from the LLM below.")
    print("      Press Enter on an empty line (or Ctrl+D) when done:")
    try:
        lines = []
        while True:
            line = input()
            if not line:
                break
            lines.append(line)
        llm_text = "\n".join(lines)
    except EOFError:
        llm_text = ""

    if not llm_text.strip():
        print("No mapping provided — clips not cut.")
        return

    mapping = json.loads(llm_text)
    if args.mapping_mode == "unit-sequential":
        first_index, last_index = _validate_unit_sequential_mapping(
            mapping, entries, args.current_track_start_index
        )
        _report_sequential_boundary(first_index, last_index)
    print(
        f"\nMapping received for {len(mapping)} entries. Cutting clips...", flush=True
    )
    cut_clips_from_mapping(
        track_path,
        mapping,
        entries,
        boundaries,
        segments,
        unit_num,
        dry_run=args.dry_run,
        output=args.output,
        rescore_model=rescore_backend,
    )


if __name__ == "__main__":
    main()
