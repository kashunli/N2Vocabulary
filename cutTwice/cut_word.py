#!/usr/bin/env python3
"""
Cut each pair clip (word + sentence) into separate word and sentence clips.

For each pair in pairs.json:
  1. Run ffmpeg silencedetect with d=0.5s on the pair clip.
  2. Find non-silent pieces, skipping any leading silence before first speech.
  3. If at least 2 pieces found:
       - piece[0]          → word clip
       - piece[1] … end   → sentence clip (single span, preserves internal pauses)
  4. Apply 0.15s padding at cut boundaries.
  5. Cut wordNNN.mp3 and sentenceNNN.mp3 alongside the pair clips.
  6. Transcribe both with whisper.cpp.
  7. Write word_path, word_transcription, sentence_path, sentence_transcription
     back into pairs.json.

Usage:
  python cut_word.py \\
      --pairs-json clips/unit7_track45/pairs.json \\
      --wcpp-binary tools/whispercpp-windows/whisper-cli.exe \\
      --wcpp-model  tools/whispercpp-windows/ggml-large-v3-turbo.bin \\
      [--silence-duration 0.5] \\
      [--noise-db -35] \\
      [--pad 0.15] \\
      [--overwrite]
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
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
    return float(json.loads(proc.stdout)["format"]["duration"])


def detect_silence(audio_path: Path, noise_db: float, min_duration: float) -> list[dict]:
    """Return list of {start, end} silence intervals (seconds)."""
    cmd = [
        "ffmpeg", "-i", str(audio_path),
        "-af", f"silencedetect=noise={noise_db}dB:d={min_duration}",
        "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    starts = [float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", proc.stderr)]
    ends   = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)",   proc.stderr)]
    return [{"start": s, "end": e} for s, e in zip(starts, ends)]


def silences_to_speech_pieces(
    silences: list[dict],
    total_duration: float,
    pad: float,
) -> list[dict]:
    """
    Derive non-silent speech pieces from silence intervals.
    Ignores a leading silence (silence whose start == 0 or near 0).
    Returns pieces with padding applied at internal boundaries.
    MIN_PIECE applied to raw (unpadded) duration.
    """
    MIN_PIECE = 0.05

    # Build raw speech spans
    raw: list[tuple[float, float]] = []
    prev_end = 0.0
    for s in silences:
        span_start = prev_end
        span_end   = s["start"]
        raw.append((span_start, span_end))
        prev_end = s["end"]
    raw.append((prev_end, total_duration))

    # Filter out slivers and the leading-silence piece (raw span at start with no speech)
    pieces = []
    for i, (rs, re_) in enumerate(raw):
        if re_ - rs < MIN_PIECE:
            continue
        # Determine if this is the very first real speech piece or track-edge
        is_first = (len(pieces) == 0)
        is_last  = (i == len(raw) - 1)

        start = rs  if is_first else rs  - pad
        end   = re_ if is_last  else re_ + pad
        start = max(0.0, start)
        end   = min(total_duration, end)
        pieces.append({"start": round(start, 3), "end": round(end, 3)})

    return pieces


def cut_clip(audio_path: Path, start: float, end: float, out_path: Path) -> None:
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
# whisper.cpp transcription
# ---------------------------------------------------------------------------

def transcribe(clip_path: Path, binary: Path, model_bin: Path, language: str = "ja") -> str:
    with tempfile.TemporaryDirectory(prefix="wcpp_") as tmpdir:
        out_prefix = Path(tmpdir) / f"result_{uuid.uuid4().hex}"
        json_path  = out_prefix.with_suffix(".json")
        cmd = [
            str(binary), "-m", str(model_bin),
            "-l", language, "-ml", "1",
            "-f", str(clip_path),
            "-oj", "-of", str(out_prefix),
            "-nt", "--no-prints",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(
                f"whisper-cli failed (rc={proc.returncode}) for {clip_path.name}\n"
                f"stderr: {proc.stderr[-400:]}"
            )
        for _ in range(20):
            if json_path.exists():
                break
            time.sleep(0.1)
        if not json_path.exists():
            raise RuntimeError(f"No JSON output at {json_path}")
        data = json.loads(json_path.read_text(encoding="utf-8", errors="replace"))

    return " ".join(
        (seg.get("text") or "").strip()
        for seg in data.get("transcription", [])
        if (seg.get("text") or "").strip()
    )


# ---------------------------------------------------------------------------
# Core split logic for one pair
# ---------------------------------------------------------------------------

def split_pair(
    pair: dict,
    output_dir: Path,
    clips_base: Path,
    binary: Path,
    model_bin: Path,
    noise_db: float,
    silence_duration: float,
    pad: float,
    language: str,
    overwrite: bool,
) -> str:
    """
    Process one pair record.  Returns a status string for logging.
    Mutates `pair` in-place with word/sentence paths, timestamps, transcriptions.
    Paths stored as relative to clips_base (POSIX slashes).
    """
    idx       = pair["index"]
    clip_path = clips_base / pair["clip_path"]

    if not clip_path.exists():
        return f"pair{idx:03d}  [SKIP — clip missing: {clip_path}]"

    already_done = pair.get("word_path") and pair.get("sentence_path")
    if already_done and not overwrite:
        return f"pair{idx:03d}  [skip — already split]"

    total = get_duration(clip_path)

    # Try silence thresholds from silence_duration down to 0.2s
    fallback_steps = [t for t in [silence_duration, 0.4, 0.3, 0.2] if t <= silence_duration]
    # deduplicate while preserving order
    seen_t: set[float] = set()
    search_thresholds: list[float] = []
    for t in fallback_steps:
        if t not in seen_t:
            seen_t.add(t); search_thresholds.append(t)

    pieces         = []
    threshold_used = silence_duration
    for t in search_thresholds:
        silences = detect_silence(clip_path, noise_db, t)
        pieces   = silences_to_speech_pieces(silences, total, pad)
        if len(pieces) >= 2:
            threshold_used = t
            break

    pair["word_split_threshold_used"] = threshold_used

    if len(pieces) < 2:
        pair["word_path"]              = None
        pair["word_transcription"]     = None
        pair["sentence_path"]          = None
        pair["sentence_transcription"] = None
        pair["split_error"]            = f"unsplittable — only {len(pieces)} piece(s) even at 0.2s threshold; needs manual review"
        return f"pair{idx:03d}  [UNSPLITTABLE — needs manual review]"

    if threshold_used != silence_duration:
        pair["split_note"] = f"split at fallback threshold {threshold_used}s (default {silence_duration}s gave <2 pieces)"

    # Word = first piece; sentence = second piece start → last piece end
    word_start     = pieces[0]["start"]
    word_end       = pieces[0]["end"]
    sentence_start = pieces[1]["start"]
    sentence_end   = pieces[-1]["end"]

    word_abs     = output_dir / f"word{idx:03d}.mp3"
    sentence_abs = output_dir / f"sentence{idx:03d}.mp3"

    try:
        cut_clip(clip_path, word_start, word_end, word_abs)
        cut_clip(clip_path, sentence_start, sentence_end, sentence_abs)
    except Exception as exc:
        pair["word_path"]              = None
        pair["word_transcription"]     = None
        pair["sentence_path"]          = None
        pair["sentence_transcription"] = None
        pair["split_error"]            = f"cut failed: {exc}"
        return f"pair{idx:03d}  [CUT ERROR — recorded and continuing]"

    pair.pop("split_error", None)
    word_text = None
    sentence_text = None
    pair.pop("word_transcription_error", None)
    pair.pop("sentence_transcription_error", None)

    try:
        word_text = transcribe(word_abs, binary, model_bin, language)
    except Exception as exc:
        pair["word_transcription_error"] = str(exc)

    try:
        sentence_text = transcribe(sentence_abs, binary, model_bin, language)
    except Exception as exc:
        pair["sentence_transcription_error"] = str(exc)

    pair["word_start"]             = word_start
    pair["word_end"]               = word_end
    pair["word_path"]              = (word_abs.relative_to(clips_base)).as_posix()
    pair["word_transcription"]     = word_text
    pair["sentence_start"]         = sentence_start
    pair["sentence_end"]           = sentence_end
    pair["sentence_path"]          = (sentence_abs.relative_to(clips_base)).as_posix()
    pair["sentence_transcription"] = sentence_text

    threshold_note = f" [fallback {threshold_used}s]" if threshold_used != silence_duration else ""
    error_note = ""
    if pair.get("word_transcription_error") or pair.get("sentence_transcription_error"):
        error_note = " [TRANSCRIPTION ERROR — clips kept]"
    return (
        f"pair{idx:03d}{threshold_note}{error_note}  word: {(word_text or '')[:30]}  |  "
        f"sentence: {(sentence_text or '')[:50]}"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Split pair clips into word + sentence.")
    parser.add_argument("--pairs-json",       required=True, type=Path)
    parser.add_argument("--wcpp-binary",      type=Path, default=None)
    parser.add_argument("--wcpp-model",       type=Path, default=None)
    parser.add_argument("--language",         default="ja")
    parser.add_argument("--silence-duration", default=0.5,   type=float,
                        help="Silence threshold to split word from sentence (default 0.5s)")
    parser.add_argument("--noise-db",         default=-35.0, type=float)
    parser.add_argument("--pad",              default=0.15,  type=float,
                        help="Padding at cut boundaries in seconds (default 0.15)")
    parser.add_argument("--overwrite",        action="store_true",
                        help="Re-split pairs that are already done")
    args = parser.parse_args()

    binary = args.wcpp_binary or Path(os.environ.get("WHISPER_CPP_BIN", ""))
    model  = args.wcpp_model  or Path(os.environ.get("WHISPER_CPP_MODEL", ""))
    if not binary or not binary.exists():
        sys.exit(f"whisper-cli not found: {binary}\nPass --wcpp-binary or set WHISPER_CPP_BIN.")
    if not model or not model.exists():
        sys.exit(f"Model not found: {model}\nPass --wcpp-model or set WHISPER_CPP_MODEL.")

    pairs_json = args.pairs_json.resolve()
    if not pairs_json.exists():
        sys.exit(f"pairs.json not found: {pairs_json}")

    manifest   = json.loads(pairs_json.read_text(encoding="utf-8"))
    pairs      = manifest.get("pairs", [])
    output_dir = pairs_json.parent
    clips_base = output_dir.parent  # paths stored relative to clips/

    print(
        f"Splitting {len(pairs)} pairs  "
        f"(silence≥{args.silence_duration}s  noise={args.noise_db}dB  pad={args.pad}s)",
        flush=True,
    )

    for pair in pairs:
        try:
            status = split_pair(
                pair, output_dir, clips_base, binary, model,
                noise_db=args.noise_db,
                silence_duration=args.silence_duration,
                pad=args.pad,
                language=args.language,
                overwrite=args.overwrite,
            )
        except Exception as exc:
            idx = pair.get("index", "?")
            pair["split_error"] = f"unexpected split failure: {exc}"
            status = f"pair{idx}  [UNEXPECTED ERROR — recorded and continuing]"
        print(f"  {status}", flush=True)

    pairs_json.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nManifest updated: {pairs_json}")


if __name__ == "__main__":
    main()
