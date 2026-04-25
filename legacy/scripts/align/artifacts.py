"""Cache artifact helpers — key generation, path construction, read/write.

All functions here are pure utilities: they compute filenames or read/write
JSON to disk. They do not call Whisper or ffmpeg. This keeps them importable
by any other module without pulling in heavy dependencies.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from align._constants import ROOT


# ---------------------------------------------------------------------------
# Key / label generation
# ---------------------------------------------------------------------------

def normalize_cache_token(value: str) -> str:
    """Normalize a filename fragment for stable cache artifact names.

    Cache files are keyed by track name, model name, and silence parameters.
    Track names contain spaces, Japanese characters, and special chars that
    make filenames fragile across shells and OS path limits. This function
    collapses everything non-alphanumeric to underscores so the cache key
    is always a safe, flat filename component.
    """
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return re.sub(r"_+", "_", cleaned) or "cache"


def whisper_cache_model_label(model_bin: Path) -> str:
    """Return a stable cache label derived from the whisper.cpp model filename."""
    return normalize_cache_token(model_bin.stem.replace("ggml-", ""))


def default_wcpp_cache_prefix(track_path: Path, unit_num: int | None, model_bin: Path) -> str:
    """Build the default cache prefix used for persisted whisper.cpp artifacts."""
    track_match = re.match(r"^(\d+)", track_path.stem)
    track_label = track_match.group(1) if track_match else normalize_cache_token(track_path.stem)
    model_label = whisper_cache_model_label(model_bin)
    if unit_num is not None:
        return f"unit{unit_num}_track_{track_label}_{model_label}_wcpp"
    return f"{normalize_cache_token(track_path.stem)}_{model_label}_wcpp"


def default_prompt_support_prefix(track_path: Path, unit_num: int | None, backend: dict) -> str:
    """Build a stable prefix for prompt support sidecar artifacts."""
    track_match = re.match(r"^(\d+)", track_path.stem)
    track_label = track_match.group(1) if track_match else normalize_cache_token(track_path.stem)
    if backend["kind"] == "whisper_cpp":
        backend_label = whisper_cache_model_label(backend["model_bin"])
    else:
        backend_label = "openai_whisper"
    if unit_num is not None:
        return f"unit{unit_num}_track_{track_label}_{backend_label}"
    return f"{normalize_cache_token(track_path.stem)}_{backend_label}"


def display_path(path: Path) -> str:
    """Return path relative to the project root when possible, for display."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------

def write_wcpp_cache_artifacts(cache_dir: Path, cache_prefix: str, segments: list[dict]) -> None:
    """Persist simplified segment JSON plus flattened transcript text."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    segments_path = cache_dir / f"{cache_prefix}_segments.json"
    transcript_path = cache_dir / f"{cache_prefix}_transcript.txt"
    segments_path.write_text(
        json.dumps(segments, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    transcript_text = "\n".join(segment["text"] for segment in segments).strip()
    transcript_path.write_text(transcript_text + ("\n" if transcript_text else ""), encoding="utf-8")


def write_silence_boundary_artifact(
    cache_dir: Path,
    cache_prefix: str,
    boundaries: list[tuple[float, str]],
    duration: float,
) -> Path:
    """Persist silence boundaries in a sidecar JSON artifact."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    silence_path = cache_dir / f"{cache_prefix}_silence_boundaries.json"
    payload = {
        "track_duration": round(duration, 3),
        "boundaries": [
            {"time": round(t, 3), "type": typ}
            for t, typ in boundaries
        ],
    }
    silence_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return silence_path


# ---------------------------------------------------------------------------
# Piece transcript cache
# ---------------------------------------------------------------------------

def piece_transcript_cache_path(
    cache_dir: Path,
    cache_prefix: str,
    silence_noise: str,
    silence_duration: float,
) -> Path:
    """Return the persisted cache path for per-piece transcriptions.

    The silence parameters (noise threshold and min duration) are baked into
    the cache filename. A different silence threshold produces different piece
    boundaries, so a cache from one silence setting must not be reused with
    another — the piece_id list would no longer match the live pieces.
    """
    silence_label = (
        f"n{normalize_cache_token(silence_noise)}"
        f"_d{normalize_cache_token(f'{silence_duration:.3f}')}"
    )
    return cache_dir / f"{cache_prefix}_{silence_label}_piece_transcripts.json"


def load_piece_transcript_cache(path: Path, pieces: list[dict]) -> list[dict] | None:
    """Load cached piece transcriptions when the piece boundaries still match.

    The cache is only valid when every piece_id and both timestamps still agree
    with the live silence detection output (within 2 ms floating-point tolerance).
    If the audio file changed or the silence parameters changed, ffmpeg will
    produce different boundaries and the old cache must be rejected — using a
    stale cache would give the LLM wrong timestamps to work with.
    """
    if not path.exists():
        return None
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(cached, list) or len(cached) != len(pieces):
        return None
    for cached_piece, piece in zip(cached, pieces):
        if not isinstance(cached_piece, dict):
            return None
        if cached_piece.get("piece_id") != piece["piece_id"]:
            return None
        if abs(float(cached_piece.get("start", -1.0)) - piece["start"]) > 0.002:
            return None
        if abs(float(cached_piece.get("end", -1.0)) - piece["end"]) > 0.002:
            return None
    return cached
