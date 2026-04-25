#!/usr/bin/env python3
"""
Cut an MP3 into pair pieces by silence detection.

Algorithm:
  1. Start with --silence-duration (default 0.9s).
  2. Detect silences; derive non-silent pieces.
  3. Strict mode: if --expected is provided, search thresholds until piece
     count matches expected.
     Just-cut mode: if --just-cut is provided, use one detection pass and
     keep whatever count the default 0.9s threshold finds.
  5. Cut each piece to <output-dir>/pair<N>.mp3.
  6. Write pairs.json with intervals and clip paths.

Usage:
  python cut_by_silence.py \\
      --track audio/unit1/track01.mp3 \\
      --expected 10 \\
      --output-dir clips/unit1 \\
      [--start-index 1] \\
      [--silence-duration 0.9] \\
      [--noise-db -35]

  python cut_by_silence.py \\
      --track audio/unit1/full_unit.mp3 \\
      --just-cut \\
      --output-dir clips/unit1_auto
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# ffmpeg helpers
# ---------------------------------------------------------------------------

def get_duration(audio_path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        str(audio_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout)
    return float(data["format"]["duration"])


def detect_silence(audio_path: Path, noise_db: float, min_duration: float) -> list[dict]:
    """Return list of {start, end} silence intervals (seconds)."""
    cmd = [
        "ffmpeg", "-i", str(audio_path),
        "-af", f"silencedetect=noise={noise_db}dB:d={min_duration}",
        "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    stderr = proc.stderr

    starts = [float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", stderr)]
    ends   = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", stderr)]

    # ffmpeg sometimes emits a trailing silence_start with no silence_end
    pairs = list(zip(starts, ends))
    return [{"start": s, "end": e} for s, e in pairs]


def silences_to_pieces(
    silences: list[dict],
    total_duration: float,
    pad: float = 0.15,
) -> list[dict]:
    """Convert silence intervals to non-silent pieces.

    Each piece is padded `pad` seconds into the surrounding silences so clips
    don't start/end abruptly.  The very first piece starts at 0.0 and the very
    last ends at total_duration (no padding needed at track edges).
    """
    MIN_PIECE = 0.05

    # Build (raw_start, raw_end) pairs from silence gaps
    raw: list[tuple[float, float]] = []
    prev_end = 0.0
    for s in silences:
        raw.append((prev_end, s["start"]))
        prev_end = s["end"]
    raw.append((prev_end, total_duration))

    pieces = []
    for i, (raw_start, raw_end) in enumerate(raw):
        if raw_end - raw_start < MIN_PIECE:  # filter on raw duration, before padding
            continue
        # Apply padding at silence boundaries only (not at track edges)
        start = raw_start if i == 0 else raw_start - pad
        end   = raw_end   if i == len(raw) - 1 else raw_end + pad
        start = max(0.0, start)
        end   = min(total_duration, end)
        pieces.append({"start": round(start, 3), "end": round(end, 3)})

    return pieces


def cut_piece(audio_path: Path, start: float, end: float, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(audio_path),
        "-ss", f"{start:.3f}",
        "-to", f"{end:.3f}",
        "-c", "copy",
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)


# ---------------------------------------------------------------------------
# Threshold search
# ---------------------------------------------------------------------------

SEARCH_STEPS = [
    0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 1.7, 2.0, 2.5, 3.0,
    0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2,
]


def find_threshold(
    audio_path: Path,
    expected: int,
    noise_db: float,
    start_duration: float,
) -> tuple[float, list[dict], float] | None:
    """
    Search for a silence_duration that yields exactly `expected` pieces.
    Returns (duration_used, silences, total_duration) or None.
    Piece counting is done without padding — padding is applied at cut time.
    """
    above = [s for s in SEARCH_STEPS if s >= start_duration]
    below = [s for s in reversed(SEARCH_STEPS) if s < start_duration]

    candidates: list[float] = []
    if start_duration not in SEARCH_STEPS:
        candidates.append(start_duration)
    a_idx = b_idx = 0
    for _ in range(len(SEARCH_STEPS) + 1):
        if a_idx < len(above):
            candidates.append(above[a_idx]); a_idx += 1
        if b_idx < len(below):
            candidates.append(below[b_idx]); b_idx += 1

    total = get_duration(audio_path)
    seen: set[float] = set()
    for dur in candidates:
        if dur in seen:
            continue
        seen.add(dur)

        silences = detect_silence(audio_path, noise_db, dur)
        pieces = silences_to_pieces(silences, total, pad=0.0)
        n = len(pieces)
        print(f"  silence_duration={dur:.2f}s → {n} pieces", flush=True)
        if n == expected:
            return dur, silences, total

    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Cut MP3 into N pieces by silence detection.")
    parser.add_argument("--track",            required=True,  type=Path, help="Input MP3 path")
    parser.add_argument("--expected",         type=int, default=None, help="Expected number of pieces (pairs). Required unless --just-cut is used")
    parser.add_argument("--just-cut",         action="store_true", help="Do one silence-detection pass and keep whatever pair count is found")
    parser.add_argument("--start-index",      default=1,      type=int,  help="Number to use for the first pair filename/index (default 1)")
    parser.add_argument("--output-dir",       required=True,  type=Path, help="Directory for pair*.mp3 and pairs.json")
    parser.add_argument("--silence-duration", default=0.9,    type=float, help="Starting silence threshold in seconds (default 0.9)")
    parser.add_argument("--noise-db",         default=-35.0,  type=float, help="Silence noise floor in dB (default -35)")
    parser.add_argument("--pad",              default=0.15,   type=float, help="Seconds of silence to keep at each clip edge (default 0.15)")
    parser.add_argument("--dry-run",          action="store_true",       help="Detect and report only; do not cut files")
    args = parser.parse_args()

    track = args.track.resolve()
    if not track.exists():
        sys.exit(f"Track not found: {track}")
    if args.expected is None and not args.just_cut:
        sys.exit("Pass --expected for strict count mode, or use --just-cut for open-ended detection.")
    if args.expected is not None and args.expected < 1:
        sys.exit("--expected must be at least 1.")
    if args.start_index < 1:
        sys.exit("--start-index must be at least 1.")

    output_dir = args.output_dir.resolve()

    print(f"Track:    {track}")
    if args.just_cut:
        print(f"Mode:     just-cut  |  silence_duration={args.silence_duration:.2f}s  |  pad={args.pad}s")
        total_duration = get_duration(track)
        silences = detect_silence(track, args.noise_db, args.silence_duration)
        threshold_used = args.silence_duration
    else:
        assert args.expected is not None
        end_index_preview = args.start_index + args.expected - 1
        print(f"Expected: {args.expected} pairs  |  index range={args.start_index}-{end_index_preview}  |  pad={args.pad}s")
        print("Searching for silence threshold...", flush=True)

        result = find_threshold(track, args.expected, args.noise_db, args.silence_duration)
        if result is None:
            sys.exit(
                f"Could not find a silence threshold that yields exactly {args.expected} pieces.\n"
                f"Check --expected or adjust --noise-db."
            )

        threshold_used, silences, total_duration = result

    # Apply padding when building final pieces
    pieces = silences_to_pieces(silences, total_duration, pad=args.pad)
    detected_pairs = len(pieces)
    end_index = args.start_index + detected_pairs - 1
    expected_pairs = detected_pairs if args.just_cut else args.expected
    print(f"\nFound: silence_duration={threshold_used:.2f}s → {detected_pairs} pieces  (index range={args.start_index}-{end_index}, pad={args.pad}s per edge)")

    clips_base = output_dir.parent  # paths stored relative to this

    def rel(p: Path) -> str:
        return p.relative_to(clips_base).as_posix()

    # Build pair records
    records = []
    for offset, piece in enumerate(pieces):
        pair_index = args.start_index + offset
        clip_path = output_dir / f"pair{pair_index:03d}.mp3"
        records.append({
            "index":         pair_index,
            "start":         piece["start"],
            "end":           piece["end"],
            "duration":      round(piece["end"] - piece["start"], 3),
            "clip_path":     rel(clip_path),
            "transcription": None,
        })

    if args.dry_run:
        print("\n[dry-run] Would cut:")
        for r in records:
            print(f"  pair{r['index']:03d}  {r['start']:.3f}s – {r['end']:.3f}s  ({r['duration']:.2f}s)")
        return

    # Cut
    print(f"\nCutting {len(pieces)} pieces → {output_dir}", flush=True)
    for r in records:
        cut_piece(track, r["start"], r["end"], clips_base / r["clip_path"])
        print(f"  ✓ pair{r['index']:03d}  {r['start']:.3f}s – {r['end']:.3f}s", flush=True)

    # Write JSON
    manifest = {
        "track":                 str(track),
        "mode":                  "just_cut" if args.just_cut else "strict_count",
        "expected_pairs":        expected_pairs,
        "expected_range":        {"start": args.start_index, "end": end_index},
        "detected_pairs":        detected_pairs,
        "silence_duration_used": threshold_used,
        "noise_db":              args.noise_db,
        "pad":                   args.pad,
        "total_duration":        round(total_duration, 3),
        "silence_intervals":     silences,
        "pairs":                 records,
    }
    json_path = output_dir / "pairs.json"
    json_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nManifest written: {json_path}")


if __name__ == "__main__":
    main()
