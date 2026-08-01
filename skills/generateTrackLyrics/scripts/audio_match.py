"""Decode audio and recover excerpt offsets with waveform correlation."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import numpy as np
from scipy.signal import correlate


SILENCE_START_RE = re.compile(r"silence_start: ([0-9.]+)")
SILENCE_END_RE = re.compile(r"silence_end: ([0-9.]+)")


class AudioMatcher:
    """Match clips against immutable tracks at a deliberately modest sample rate.

    The clips were encoded from the same CD tracks. At 8 kHz, normalized
    waveform correlation retains enough speech detail for a decisive match but
    keeps a whole unit of decoded source audio inexpensive to hold in memory.
    """

    def __init__(self, sample_rate: int = 8_000) -> None:
        self.sample_rate = sample_rate
        self._source_cache: dict[str, np.ndarray] = {}

    def clear_sources(self) -> None:
        """Release decoded tracks between units to bound memory use."""
        self._source_cache.clear()

    def decode(self, path: str | Path, *, source: bool = False) -> np.ndarray:
        resolved = str(Path(path).resolve())
        if source and resolved in self._source_cache:
            return self._source_cache[resolved]
        result = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                resolved,
                "-ac",
                "1",
                "-ar",
                str(self.sample_rate),
                "-f",
                "f32le",
                "-",
            ],
            check=True,
            capture_output=True,
        )
        audio = np.frombuffer(result.stdout, dtype="<f4").copy()
        if source:
            self._source_cache[resolved] = audio
        return audio

    def match(self, source_path: str | Path, query_path: str | Path) -> tuple[float, float, float]:
        source = self.decode(source_path, source=True)
        query = self.decode(query_path)
        offset, score = normalized_offset(source, query, self.sample_rate)
        return offset, score, len(query) / self.sample_rate

    def match_candidates(
        self, source_paths: list[str], query_path: str | Path
    ) -> tuple[str, float, float, float, list[dict]]:
        query = self.decode(query_path)
        results: list[dict] = []
        for source_path in source_paths:
            source = self.decode(source_path, source=True)
            offset, score = normalized_offset(source, query, self.sample_rate)
            results.append({"source_audio": source_path, "offset": offset, "score": score})
        results.sort(key=lambda item: item["score"], reverse=True)
        winner = results[0]
        return (
            winner["source_audio"],
            winner["offset"],
            winner["score"],
            len(query) / self.sample_rate,
            results,
        )

    def speech_segments(
        self,
        source_path: str | Path,
        *,
        noise: str = "-38dB",
        minimum_silence: float = 0.12,
    ) -> list[tuple[float, float]]:
        """Return non-silent regions using the same FFmpeg evidence as cutting."""
        resolved = str(Path(source_path).resolve())
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-i",
                resolved,
                "-af",
                f"silencedetect=noise={noise}:d={minimum_silence}",
                "-f",
                "null",
                "-",
            ],
            check=True,
            text=True,
            capture_output=True,
        )
        starts = [float(value) for value in SILENCE_START_RE.findall(result.stderr)]
        ends = [float(value) for value in SILENCE_END_RE.findall(result.stderr)]
        duration = len(self.decode(source_path, source=True)) / self.sample_rate

        silences: list[tuple[float, float]] = []
        end_index = 0
        for start in starts:
            while end_index < len(ends) and ends[end_index] <= start:
                end_index += 1
            end = ends[end_index] if end_index < len(ends) else duration
            silences.append((start, end))
            end_index += 1

        speech: list[tuple[float, float]] = []
        cursor = 0.0
        for start, end in silences:
            if start > cursor:
                speech.append((cursor, start))
            cursor = max(cursor, end)
        if cursor < duration:
            speech.append((cursor, duration))
        return [(start, end) for start, end in speech if end - start >= 0.08]


def normalized_offset(
    source: np.ndarray, query: np.ndarray, sample_rate: int
) -> tuple[float, float]:
    """Return query offset and normalized correlation in the source.

    Moving-window energy normalization matters because track loudness varies.
    The source and query are mean-centered to remove small decoder DC offsets.
    """
    if len(query) == 0 or len(source) < len(query):
        raise ValueError("Query must contain audio and fit inside the source track")
    query64 = query.astype(np.float64) - float(np.mean(query))
    source64 = source.astype(np.float64) - float(np.mean(source))
    query_energy = float(np.dot(query64, query64))
    if query_energy <= 1e-12:
        raise ValueError("Query contains no usable audio energy")

    raw = correlate(source64, query64, mode="valid", method="fft")
    energy_prefix = np.concatenate(([0.0], np.cumsum(source64 * source64)))
    moving_energy = energy_prefix[len(query64) :] - energy_prefix[: -len(query64)]
    scores = raw / np.sqrt(np.maximum(moving_energy, 1e-12) * query_energy)
    index = int(np.argmax(scores))
    return index / sample_rate, float(scores[index])


def padded_speech_bounds(
    segment: tuple[float, float], next_start: float | None = None
) -> tuple[float, float]:
    """Apply the reviewed 100 ms lead / adaptive 200 ms tail policy."""
    start, end = segment
    padded_start = max(0.0, start - 0.10)
    trailing = 0.20
    if next_start is not None:
        following_silence = max(0.0, next_start - end)
        trailing = min(trailing, following_silence / 2.0)
    return padded_start, end + trailing
