"""ffmpeg-based silence detection and speech piece enumeration.

These functions are the timing backbone of the alignment pipeline. Every clip
boundary is ultimately derived from the silence edges detected here, not from
Whisper's segment timestamps. This separation is deliberate: Whisper tells us
*what* was said; ffmpeg tells us *when* the silence is.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

_SILENCE_START = re.compile(r"silence_start: ([0-9.]+)")
_SILENCE_END = re.compile(r"silence_end: ([0-9.]+)\s+\|")


def detect_silence_boundaries(
    track_path: Path,
    noise: str = "-32dB",
    min_dur: float = 0.25,
) -> tuple[list[tuple[float, str]], float]:
    """Run ffmpeg silencedetect and return ordered (time, type) boundary list.

    Returns boundaries plus total track duration. The duration is appended as a
    synthetic "end" boundary so downstream code can treat the track end the same
    as any other silence edge.

    Default min_dur=0.25s is the recommended value for Japanese audio — 0.18s
    (ffmpeg default) cuts mid-word on final consonants. Pass --silence-duration
    to override when working with unusually dense or sparse audio.
    """
    cmd = [
        "ffmpeg", "-i", str(track_path),
        "-af", f"silencedetect=noise={noise}:d={min_dur}",
        "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"ffmpeg silencedetect failed: {proc.stderr}")

    boundaries: list[tuple[float, str]] = []
    for line in proc.stderr.splitlines():
        m = _SILENCE_START.search(line)
        if m:
            boundaries.append((float(m.group(1)), "start"))
        m = _SILENCE_END.search(line)
        if m:
            boundaries.append((float(m.group(1)), "end"))
    boundaries.sort(key=lambda x: x[0])

    duration = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(track_path)],
        text=True,
    ).strip())
    boundaries.append((duration, "end"))

    return boundaries, duration


def speech_regions(
    boundaries: list[tuple[float, str]],
    duration: float,
) -> list[tuple[float, float]]:
    """Convert silence boundaries to speech regions [(start, end), ...].

    ffmpeg's silencedetect names boundaries from the silence's perspective:
      "silence_end"   = silence ends   → speech begins  (type="end")
      "silence_start" = silence starts → speech ends    (type="start")
    We walk the boundary list and collect speech windows accordingly.
    """
    regions = []
    speech_start = None
    for t, typ in boundaries:
        if typ == "end":
            speech_start = t
        elif typ == "start" and speech_start is not None:
            regions.append((speech_start, t))
            speech_start = None
    return regions


def enumerate_speech_pieces(
    boundaries: list[tuple[float, str]],
    duration: float,
) -> list[dict]:
    """Return ordered non-silence pieces with stable integer piece_ids.

    piece_id is simply the 0-based position in the list. It is stable as long
    as the silence boundaries don't change (same audio + same ffmpeg parameters),
    so it can be used as a cache key and as the primary unit in LLM prompts.
    """
    return [
        {"piece_id": idx, "start": start, "end": end}
        for idx, (start, end) in enumerate(speech_regions(boundaries, duration))
    ]
