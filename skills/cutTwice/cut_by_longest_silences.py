#!/usr/bin/env python3
"""
Cut an audio track by choosing the longest detected silence intervals.

This is an experimental alternative to cut_by_silence.py.  The original
script searches for a silence-duration threshold that happens to produce the
expected number of pieces.  This script uses a different idea:

  1. Detect many silence intervals in one pass, using a lower threshold such
     as d=0.5s.
  2. Treat the longest internal silences as the most likely word-pair
     separators.
  3. For N expected word/sentence pairs, choose N - 1 separator silences.
  4. Cut the spans between those selected separators.

The script is intentionally verbose and conservative because it is meant as a
future repair / experimentation tool.  It does not replace the existing
cutTwice workflow.

Example:
  python skills/cutTwice/cut_by_longest_silences.py \\
      --track "audio/unit1/track01.mp3" \\
      --expected 10 \\
      --start-index 1 \\
      --output-dir "clips/unit1_track01_longest" \\
      --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def get_duration(audio_path: Path) -> float:
    """Return the media duration in seconds using ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        str(audio_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout)
    return float(data["format"]["duration"])


def detect_silence(
    audio_path: Path,
    noise_db: float,
    min_duration: float,
    total_duration: float,
) -> list[dict[str, float]]:
    """
    Return every ffmpeg silence interval matching the provided thresholds.

    ffmpeg's silencedetect filter prints messages such as:

      silence_start: 12.345
      silence_end: 13.901 | silence_duration: 1.556

    We parse those messages from stderr.  If the track ends during silence,
    ffmpeg may emit a final silence_start without a matching silence_end; in
    that case we close the interval at the known track duration.
    """
    cmd = [
        "ffmpeg",
        "-i",
        str(audio_path),
        "-af",
        f"silencedetect=noise={noise_db}dB:d={min_duration}",
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.splitlines()[-12:])
        sys.exit(f"ffmpeg silencedetect failed for {audio_path}\n{tail}")

    starts = [float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", proc.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", proc.stderr)]

    intervals: list[dict[str, float]] = []
    for start, end in zip(starts, ends):
        intervals.append(
            {
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(end - start, 3),
            }
        )

    if len(starts) > len(ends):
        start = starts[-1]
        intervals.append(
            {
                "start": round(start, 3),
                "end": round(total_duration, 3),
                "duration": round(total_duration - start, 3),
            }
        )

    return intervals


def choose_longest_internal_silences(
    intervals: list[dict[str, float]],
    expected_pairs: int,
    total_duration: float,
    edge_margin: float,
) -> list[dict[str, Any]]:
    """
    Choose expected_pairs - 1 silence intervals as pair separators.

    Leading and trailing silences are usually not useful separators: they are
    the quiet before the first item or after the last item.  We exclude any
    silence that touches the edge margin, rank the remaining candidates by
    duration, keep the longest separators, then sort them back into playback
    order before cutting.
    """
    separator_count = expected_pairs - 1
    if separator_count == 0:
        return []

    candidates = [
        interval
        for interval in intervals
        if interval["end"] > edge_margin
        and interval["start"] < total_duration - edge_margin
    ]

    if len(candidates) < separator_count:
        sys.exit(
            f"Only found {len(candidates)} internal silence candidates, "
            f"but expected {separator_count} separators for {expected_pairs} pairs. "
            "Try lowering --detect-duration or adjusting --noise-db."
        )

    ranked = sorted(candidates, key=lambda item: item["duration"], reverse=True)
    selected = ranked[:separator_count]

    # Add rank metadata so the manifest shows why a separator was chosen.
    selected_ids = {id(item): rank for rank, item in enumerate(ranked, start=1)}
    with_rank = [
        {
            "start": item["start"],
            "end": item["end"],
            "duration": item["duration"],
            "duration_rank": selected_ids[id(item)],
        }
        for item in selected
    ]
    return sorted(with_rank, key=lambda item: item["start"])


def build_pair_spans(
    separators: list[dict[str, Any]],
    total_duration: float,
    pad: float,
) -> list[dict[str, float]]:
    """
    Convert selected separator silences into pair clip spans.

    The raw pair boundaries use the full silence interval as the gap:

      pair A ends at separator.start
      pair B starts at separator.end

    Then each output clip is padded slightly into the surrounding silence so
    the speech does not feel clipped at the edge.
    """
    raw_boundaries: list[tuple[float, float]] = []
    previous_start = 0.0

    for separator in separators:
        raw_boundaries.append((previous_start, float(separator["start"])))
        previous_start = float(separator["end"])

    raw_boundaries.append((previous_start, total_duration))

    spans = []
    last_index = len(raw_boundaries) - 1
    for index, (raw_start, raw_end) in enumerate(raw_boundaries):
        start = raw_start if index == 0 else raw_start - pad
        end = raw_end if index == last_index else raw_end + pad
        start = max(0.0, start)
        end = min(total_duration, end)
        spans.append(
            {
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(end - start, 3),
                "raw_start": round(raw_start, 3),
                "raw_end": round(raw_end, 3),
                "raw_duration": round(raw_end - raw_start, 3),
            }
        )

    return spans


def cut_piece(audio_path: Path, start: float, end: float, out_path: Path) -> None:
    """Copy the requested audio time span to an MP3 clip."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(audio_path),
        "-ss",
        f"{start:.3f}",
        "-to",
        f"{end:.3f}",
        "-c",
        "copy",
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Cut an audio track into expected pairs by selecting the longest "
            "detected internal silence intervals."
        )
    )
    parser.add_argument("--track", required=True, type=Path, help="Input audio path")
    parser.add_argument("--expected", required=True, type=int, help="Expected pair count")
    parser.add_argument(
        "--start-index",
        default=1,
        type=int,
        help="Number for the first pair filename/index (default: 1)",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory for pair*.mp3 and pairs.json",
    )
    parser.add_argument(
        "--detect-duration",
        default=0.5,
        type=float,
        help="Minimum silence duration to collect as a candidate (default: 0.5)",
    )
    parser.add_argument(
        "--noise-db",
        default=-35.0,
        type=float,
        help="Silence noise floor in dB (default: -35)",
    )
    parser.add_argument(
        "--edge-margin",
        default=0.25,
        type=float,
        help="Ignore silence intervals touching this many seconds near track edges",
    )
    parser.add_argument(
        "--pad",
        default=0.15,
        type=float,
        help="Seconds of silence to keep at each clip edge (default: 0.15)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report the selected separators and cuts without writing files",
    )
    args = parser.parse_args()

    track = args.track.resolve()
    if not track.exists():
        sys.exit(f"Track not found: {track}")
    if args.expected < 1:
        sys.exit("--expected must be at least 1.")
    if args.start_index < 1:
        sys.exit("--start-index must be at least 1.")
    if args.detect_duration <= 0:
        sys.exit("--detect-duration must be greater than 0.")
    if args.pad < 0:
        sys.exit("--pad cannot be negative.")

    output_dir = args.output_dir.resolve()
    total_duration = get_duration(track)

    print(f"Track:    {track}")
    print(
        "Mode:     longest-silences"
        f"  |  expected={args.expected}"
        f"  |  detect_duration={args.detect_duration:.2f}s"
        f"  |  noise={args.noise_db:g}dB"
    )

    all_silences = detect_silence(
        track,
        noise_db=args.noise_db,
        min_duration=args.detect_duration,
        total_duration=total_duration,
    )
    separators = choose_longest_internal_silences(
        all_silences,
        expected_pairs=args.expected,
        total_duration=total_duration,
        edge_margin=args.edge_margin,
    )
    spans = build_pair_spans(separators, total_duration=total_duration, pad=args.pad)

    clips_base = output_dir.parent

    def rel(path: Path) -> str:
        return path.relative_to(clips_base).as_posix()

    records = []
    for offset, span in enumerate(spans):
        pair_index = args.start_index + offset
        clip_path = output_dir / f"pair{pair_index:03d}.mp3"
        records.append(
            {
                "index": pair_index,
                "start": span["start"],
                "end": span["end"],
                "duration": span["duration"],
                "raw_start": span["raw_start"],
                "raw_end": span["raw_end"],
                "raw_duration": span["raw_duration"],
                "clip_path": rel(clip_path),
                "transcription": None,
            }
        )

    end_index = args.start_index + len(records) - 1
    print(
        f"\nDetected {len(all_silences)} candidate silences; "
        f"selected {len(separators)} separators -> {len(records)} pairs "
        f"(index range={args.start_index}-{end_index})."
    )

    if separators:
        print("\nSelected separators:")
        for separator in separators:
            print(
                f"  rank {separator['duration_rank']:>2}: "
                f"{separator['start']:.3f}s - {separator['end']:.3f}s "
                f"({separator['duration']:.3f}s)"
            )

    print("\nCuts:")
    for record in records:
        print(
            f"  pair{record['index']:03d}  "
            f"{record['start']:.3f}s - {record['end']:.3f}s "
            f"({record['duration']:.2f}s)"
        )

    if args.dry_run:
        print("\n[dry-run] No clips or manifest written.")
        return

    print(f"\nCutting {len(records)} pieces -> {output_dir}", flush=True)
    for record in records:
        cut_piece(track, record["start"], record["end"], clips_base / record["clip_path"])
        print(
            f"  pair{record['index']:03d}  "
            f"{record['start']:.3f}s - {record['end']:.3f}s",
            flush=True,
        )

    manifest = {
        "track": str(track),
        "mode": "longest_silences",
        "expected_pairs": args.expected,
        "expected_range": {"start": args.start_index, "end": end_index},
        "detected_pairs": len(records),
        "detect_duration_used": args.detect_duration,
        "noise_db": args.noise_db,
        "edge_margin": args.edge_margin,
        "pad": args.pad,
        "total_duration": round(total_duration, 3),
        "silence_intervals": all_silences,
        "selected_separator_intervals": separators,
        "pairs": records,
    }

    json_path = output_dir / "pairs.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nManifest written: {json_path}")


if __name__ == "__main__":
    main()
