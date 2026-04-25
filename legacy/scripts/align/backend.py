"""Whisper transcription backend abstraction.

Provides a unified backend handle (dict) that the rest of the pipeline uses.
Two backends are supported:
  - "openai"      — Python `whisper` package (CPU / NVIDIA CUDA)
  - "whisper_cpp" — whisper.cpp CLI via subprocess (Vulkan GPU on AMD)

Two backends exist because the Python `whisper` package does not support AMD
GPUs. The whisper.cpp backend runs as a subprocess and uses the Vulkan compute
path, giving ~10x faster transcription on the AMD RX 6900/6950 XT. The OpenAI
backend is kept for environments without the whisper.cpp build.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from align.artifacts import default_wcpp_cache_prefix, write_wcpp_cache_artifacts


# ---------------------------------------------------------------------------
# Encoding-tolerant JSON reader
# ---------------------------------------------------------------------------

def _read_json_text(path: Path) -> str:
    """Read whisper.cpp JSON output while tolerating Windows encoding edge cases.

    whisper.cpp on Windows produces mostly UTF-8 but token-level byte sequences
    can be truncated inside the detailed token list. BOM and UTF-16 are also
    possible depending on the build. We try the most likely encodings in order
    and fall back to UTF-8 with replacement so the JSON remains parseable.
    """
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig", errors="replace")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")) or raw.count(b"\x00") > max(2, len(raw) // 8):
        for encoding in ("utf-16", "utf-16-le", "utf-16-be"):
            try:
                return raw.decode(encoding, errors="replace")
            except UnicodeDecodeError:
                continue
    for encoding in ("utf-8", "cp932", "shift_jis", "cp936", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Backend loader
# ---------------------------------------------------------------------------

def load_backend(
    kind: str = "openai",
    model_name: str = "base",
    device: str = "cpu",
    wcpp_binary: str | Path | None = None,
    wcpp_model: str | Path | None = None,
) -> dict:
    """Load a transcription backend handle.

    Returns a dict with a `kind` tag and backend-specific fields:
      - {"kind": "openai",      "model": <whisper.model>}
      - {"kind": "whisper_cpp", "binary": <Path>, "model_bin": <Path>}

    The handle is passed to `transcribe_full_track()` and `rescore_clip()`.
    For whisper_cpp, `--wcpp-binary` / `--wcpp-model` CLI flags or the env
    vars `WHISPER_CPP_BIN` / `WHISPER_CPP_MODEL` supply paths.
    """
    if kind == "openai":
        import whisper
        return {"kind": "openai", "model": whisper.load_model(model_name, device=device)}
    if kind == "whisper_cpp":
        bin_path = Path(wcpp_binary) if wcpp_binary else Path(os.environ.get("WHISPER_CPP_BIN", ""))
        mdl_path = Path(wcpp_model) if wcpp_model else Path(os.environ.get("WHISPER_CPP_MODEL", ""))
        if not str(bin_path) or not bin_path.exists():
            raise FileNotFoundError(
                f"whisper.cpp binary not found: {bin_path!s}\n"
                f"Pass --wcpp-binary or set WHISPER_CPP_BIN."
            )
        if not str(mdl_path) or not mdl_path.exists():
            raise FileNotFoundError(
                f"whisper.cpp model not found: {mdl_path!s}\n"
                f"Pass --wcpp-model or set WHISPER_CPP_MODEL."
            )
        return {"kind": "whisper_cpp", "binary": bin_path, "model_bin": mdl_path}
    raise ValueError(f"Unknown backend kind: {kind!r} (expected 'openai' or 'whisper_cpp')")


# ---------------------------------------------------------------------------
# whisper.cpp subprocess transcription
# ---------------------------------------------------------------------------

def _transcribe_wcpp(
    track_path: Path,
    binary: Path,
    model_bin: Path,
    cache_dir: Path | None = None,
    cache_prefix: str | None = None,
) -> list[dict]:
    """Shell out to whisper.cpp and parse its JSON output into our segment shape.

    whisper.cpp writes its output to disk rather than stdout, so we pass a temp
    file base (-of) and poll until the file appears. The poll is needed because
    on Windows the process can exit slightly before the filesystem flushes the
    last bytes.

    `-ml 1` requests the finest possible segment granularity (max 1 token per
    segment). Finer segments give better start/end timestamps for local repair
    work, where we need to know exactly where within a piece a word boundary is.
    `-nt` suppresses per-segment timestamps on stdout so the terminal isn't
    flooded during batch runs.
    """
    with tempfile.TemporaryDirectory(prefix="wcpp_") as tmpdir:
        out_prefix = Path(tmpdir) / f"result_{uuid.uuid4().hex}"
        json_path = out_prefix.with_suffix(".json")
        cmd = [
            str(binary),
            "-m", str(model_bin),
            "-l", "ja",
            "-ml", "1",
            "-f", str(track_path),
            "-oj",
            "-of", str(out_prefix),
            "-nt",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(
                f"whisper-cli failed (rc={proc.returncode})\n"
                f"cmd: {' '.join(cmd)}\n"
                f"stderr:\n{proc.stderr}"
            )
        for _ in range(20):
            if json_path.exists():
                break
            time.sleep(0.1)
        if not json_path.exists():
            raise RuntimeError(f"whisper-cli produced no JSON at {json_path}")
        data = json.loads(_read_json_text(json_path))

    segments = []
    for seg in data.get("transcription", []):
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        offsets = seg.get("offsets", {})
        if "from" not in offsets or "to" not in offsets:
            continue
        segments.append({
            "start": offsets["from"] / 1000.0,
            "end": offsets["to"] / 1000.0,
            "text": text,
        })
    if cache_dir is not None:
        prefix = cache_prefix or default_wcpp_cache_prefix(track_path, None, model_bin)
        write_wcpp_cache_artifacts(cache_dir, prefix, segments)
    return segments


# ---------------------------------------------------------------------------
# Unified full-track transcription
# ---------------------------------------------------------------------------

def transcribe_full_track(
    track_path: Path,
    backend: dict | None = None,
    model_name: str = "base",
    device: str = "cpu",
    model=None,
    cache_dir: Path | None = None,
    cache_prefix: str | None = None,
) -> list[dict]:
    """Full-track transcription via the active backend.

    `backend` is a dict from `load_backend()`. For backward compatibility,
    callers that pass a raw Python-whisper model via `model=` still work —
    it gets wrapped as an openai-kind backend on the fly.
    """
    if backend is None:
        if model is None:
            backend = load_backend("openai", model_name=model_name, device=device)
        else:
            backend = {"kind": "openai", "model": model}

    if backend["kind"] == "openai":
        result = backend["model"].transcribe(
            str(track_path), language="ja", word_timestamps=True, verbose=False
        )
        segments = []
        for seg in result["segments"]:
            text = seg["text"].strip()
            if not text:
                continue
            segments.append({
                "start": float(seg["start"]),
                "end": float(seg["end"]),
                "text": text,
            })
        return segments

    return _transcribe_wcpp(
        track_path,
        backend["binary"],
        backend["model_bin"],
        cache_dir=cache_dir,
        cache_prefix=cache_prefix,
    )
