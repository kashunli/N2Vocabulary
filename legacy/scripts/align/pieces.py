"""Per-speech-piece transcription with caching.

Why cut and transcribe each piece instead of slicing the full-track transcript?
  1. Whisper's segment timestamps are often off by 0.1-0.5s, especially at the
     start of a segment. Cutting a fresh clip and transcribing it from t=0
     removes that offset error entirely.
  2. Short isolated clips (0.5-3s) give Whisper much less ambiguous context, so
     it makes fewer substitution errors on rare vocabulary words.
The tradeoff is time: N subprocess calls instead of 1. The piece transcript
cache avoids re-running this for subsequent LLM attempts on the same track.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from align.artifacts import piece_transcript_cache_path, load_piece_transcript_cache
from align.backend import transcribe_full_track
from align.cut import cut_clip


def transcribe_speech_pieces(
    track_path: Path,
    pieces: list[dict],
    backend: dict,
    silence_noise: str,
    silence_duration: float,
    cache_dir: Path | None = None,
    cache_prefix: str | None = None,
) -> tuple[list[dict], Path | None]:
    """Cut every speech piece to a temp file and transcribe it individually.

    Returns (piece_transcripts, cache_path). cache_path is None when caching
    is disabled. Each element of piece_transcripts has the piece's original
    boundaries plus the transcript text and segment count from Whisper.
    """
    cache_path = None
    if cache_dir is not None and cache_prefix is not None:
        cache_path = piece_transcript_cache_path(
            cache_dir, cache_prefix,
            silence_noise=silence_noise,
            silence_duration=silence_duration,
        )
        cached = load_piece_transcript_cache(cache_path, pieces)
        if cached is not None:
            return cached, cache_path

    piece_transcripts: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="piece_clips_") as tmpdir:
        temp_dir = Path(tmpdir)
        for piece in pieces:
            clip_path = temp_dir / f"piece_{piece['piece_id']:03d}.mp3"
            transcript_text = ""
            segment_count = 0
            if cut_clip(track_path, clip_path, piece["start"], piece["end"]):
                segments = transcribe_full_track(clip_path, backend=backend)
                segment_count = len(segments)
                transcript_text = "".join(s.get("text", "") for s in segments).strip()
            piece_transcripts.append({
                "piece_id": piece["piece_id"],
                "start": piece["start"],
                "end": piece["end"],
                "duration": round(piece["end"] - piece["start"], 3),
                "text": transcript_text,
                "segment_count": segment_count,
            })

    if cache_path is not None:
        cache_path.write_text(
            json.dumps(piece_transcripts, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return piece_transcripts, cache_path
