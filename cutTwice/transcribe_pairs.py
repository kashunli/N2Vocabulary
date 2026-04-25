#!/usr/bin/env python3
"""
Transcribe each pair clip in a pairs.json manifest using whisper.cpp.

Reads pairs.json, transcribes each clip, and writes the transcription
back into the "transcription" field of each pair record.

Usage:
  python transcribe_pairs.py \\
      --pairs-json clips/unit1/pairs.json \\
      --wcpp-binary tools/whispercpp-windows/whisper-cli.exe \\
      --wcpp-model  tools/whispercpp-windows/ggml-large-v3-turbo.bin \\
      [--language ja]
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
from typing import Any


# ---------------------------------------------------------------------------
# whisper.cpp transcription
# ---------------------------------------------------------------------------

def transcribe_clip(
    clip_path: Path,
    binary: Path,
    model_bin: Path,
    language: str = "ja",
) -> tuple[str, list[dict[str, Any]]]:
    """
    Run whisper-cli on a single clip and return the plain transcript text.
    Uses -ml 1 for fine segment granularity (consistent with main pipeline).
    Returns concatenated text plus raw Whisper segment objects for review.
    """
    with tempfile.TemporaryDirectory(prefix="wcpp_") as tmpdir:
        out_prefix = Path(tmpdir) / f"result_{uuid.uuid4().hex}"
        json_path = out_prefix.with_suffix(".json")

        cmd = [
            str(binary),
            "-m", str(model_bin),
            "-l", language,
            "-ml", "1",
            "-f", str(clip_path),
            "-oj",
            "-of", str(out_prefix),
            "-nt",
            "--no-prints",
        ]

        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(
                f"whisper-cli failed (rc={proc.returncode}) for {clip_path.name}\n"
                f"stderr: {proc.stderr[-500:]}"
            )

        # Wait for file flush (Windows can be slow)
        for _ in range(20):
            if json_path.exists():
                break
            time.sleep(0.1)

        if not json_path.exists():
            raise RuntimeError(f"whisper-cli produced no JSON at {json_path}")

        data = json.loads(json_path.read_text(encoding="utf-8", errors="replace"))

    segments = data.get("transcription", [])
    text = " ".join(
        (seg.get("text") or "").strip()
        for seg in segments
        if (seg.get("text") or "").strip()
    )
    return text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe pair clips listed in pairs.json.")
    parser.add_argument("--pairs-json",  required=True, type=Path, help="Path to pairs.json from cut_by_silence.py")
    parser.add_argument("--wcpp-binary", type=Path, default=None,  help="Path to whisper-cli.exe (or set WHISPER_CPP_BIN)")
    parser.add_argument("--wcpp-model",  type=Path, default=None,  help="Path to ggml model bin (or set WHISPER_CPP_MODEL)")
    parser.add_argument("--language",    default="ja",             help="Whisper language code (default: ja)")
    parser.add_argument("--overwrite",   action="store_true",      help="Re-transcribe clips that already have a transcription")
    args = parser.parse_args()

    # Resolve binary / model from args or env
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
    clips_base = pairs_json.parent.parent  # paths in JSON are relative to clips/

    total   = len(pairs)
    skipped = 0

    print(f"Transcribing {total} clips  (model: {model.name})", flush=True)

    for pair in pairs:
        idx       = pair["index"]
        clip_path = clips_base / pair["clip_path"]

        if pair.get("transcription") and not args.overwrite:
            print(f"  pair{idx:03d}  [skip — already transcribed]")
            skipped += 1
            continue

        if not clip_path.exists():
            print(f"  pair{idx:03d}  [MISSING clip: {clip_path}]")
            pair["transcription"] = None
            pair["transcription_error"] = f"missing clip: {clip_path}"
            continue

        try:
            text = transcribe_clip(clip_path, binary, model, language=args.language)
            pair["transcription"] = text
            pair.pop("transcription_error", None)
            print(f"  pair{idx:03d}  {text[:80]}", flush=True)
        except RuntimeError as e:
            print(f"  pair{idx:03d}  [ERROR] {e}", flush=True)
            pair["transcription"] = None
            pair["transcription_error"] = str(e)

    # Save updated manifest
    pairs_json.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    done = total - skipped
    print(f"\nDone. {done} transcribed, {skipped} skipped. Manifest updated: {pairs_json}")


if __name__ == "__main__":
    main()
