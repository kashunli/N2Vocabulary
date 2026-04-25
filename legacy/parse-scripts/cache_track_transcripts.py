#!/usr/bin/env python3
"""Save per-track transcription caches for a unit review JSON.

The primary use case is whisper.cpp on Windows with Vulkan enabled, saving:

- raw ``-oj`` JSON
- normalized ``segments.json``
- flattened transcript text
- a manifest summarizing the run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from align import ROOT, _read_json_text, load_backend, transcribe_full_track


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cache per-track transcription outputs.")
    parser.add_argument("--review-json", type=Path, required=True)
    parser.add_argument("--unit", type=int, required=True)
    parser.add_argument("--backend", choices=["openai", "whisper_cpp"], default="whisper_cpp")
    parser.add_argument("--model", default="base", help="OpenAI Whisper model name")
    parser.add_argument("--device", default="cpu", help="OpenAI Whisper device")
    parser.add_argument("--wcpp-binary", type=Path, default=None)
    parser.add_argument("--wcpp-model", type=Path, default=None)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "output" / "whisper_cache")
    parser.add_argument(
        "--tracks",
        nargs="*",
        default=[],
        help="Optional track filename filters, e.g. '08 1-08.mp3'",
    )
    return parser


def backend_slug(backend: dict[str, Any], args: argparse.Namespace) -> str:
    if backend["kind"] == "openai":
        return args.model
    model_name = Path(backend["model_bin"]).stem
    if model_name.startswith("ggml-"):
        model_name = model_name[len("ggml-") :]
    model_name = model_name.replace("-", "_")
    return f"{model_name}_wcpp"


def collect_tracks(review_rows: list[dict[str, Any]], filters: set[str]) -> list[dict[str, str]]:
    seen: dict[str, dict[str, str]] = {}
    for row in review_rows:
        track_name = row["track_name"]
        if filters and track_name not in filters:
            continue
        seen.setdefault(
            track_name,
            {"track_name": track_name, "track_path": row["track_path"].replace("\\", "/")},
        )
    def track_sort_key(item: dict[str, str]) -> tuple[int, str]:
        prefix = item["track_name"].split()[0]
        try:
            return int(prefix), item["track_name"]
        except ValueError:
            return 9999, item["track_name"]
    return sorted(seen.values(), key=track_sort_key)


def audio_duration_seconds(path: Path) -> float | None:
    try:
        value = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            text=True,
        ).strip()
    except Exception:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def write_wcpp_raw_json(
    track_path: Path,
    output_path: Path,
    binary: Path,
    model_bin: Path,
) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prefix = output_path.with_suffix("")
    cmd = [
        str(binary),
        "-m",
        str(model_bin),
        "-l",
        "ja",
        "-ml",
        "1",
        "-f",
        str(track_path),
        "-oj",
        "-of",
        str(prefix),
        "-nt",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"whisper-cli failed for {track_path.name} (rc={proc.returncode})\n{proc.stderr}"
        )
    return json.loads(_read_json_text(output_path))


def segments_from_raw(data: dict[str, Any]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for seg in data.get("transcription", []):
        text = (seg.get("text") or "").strip()
        offsets = seg.get("offsets", {})
        if not text or "from" not in offsets or "to" not in offsets:
            continue
        segments.append(
            {
                "start": round(offsets["from"] / 1000.0, 3),
                "end": round(offsets["to"] / 1000.0, 3),
                "text": text,
            }
        )
    return segments


def main() -> None:
    args = build_parser().parse_args()
    review_rows = json.loads(args.review_json.read_text(encoding="utf-8"))
    tracks = collect_tracks(review_rows, set(args.tracks))
    backend = load_backend(
        args.backend,
        model_name=args.model,
        device=args.device,
        wcpp_binary=args.wcpp_binary,
        wcpp_model=args.wcpp_model,
    )
    slug = backend_slug(backend, args)
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    manifest: list[dict[str, Any]] = []
    for item in tracks:
        track_name = item["track_name"]
        track_num = track_name.split()[0]
        track_path = ROOT / item["track_path"]

        raw_json = args.cache_dir / f"unit{args.unit}_track_{track_num}_{slug}_ml1.json"
        segments_json = args.cache_dir / f"unit{args.unit}_track_{track_num}_{slug}_segments.json"
        transcript_txt = args.cache_dir / f"unit{args.unit}_track_{track_num}_{slug}_transcript.txt"

        started = time.perf_counter()
        if backend["kind"] == "whisper_cpp":
            raw = write_wcpp_raw_json(
                track_path=track_path,
                output_path=raw_json,
                binary=backend["binary"],
                model_bin=backend["model_bin"],
            )
            segments = segments_from_raw(raw)
        else:
            segments = transcribe_full_track(track_path, backend=backend)
            raw = {"segments": segments}
            raw_json.write_text(
                json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        elapsed = time.perf_counter() - started

        transcript = "".join(seg.get("text", "") for seg in segments).strip()
        segments_json.write_text(
            json.dumps(segments, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        transcript_txt.write_text(transcript + "\n", encoding="utf-8")

        manifest.append(
            {
                "track": track_name,
                "track_num": track_num,
                "raw_json_file": raw_json.name,
                "segments_file": segments_json.name,
                "transcript_file": transcript_txt.name,
                "segment_count": len(segments),
                "audio_seconds_approx": round(audio_duration_seconds(track_path) or 0.0, 2),
                "elapsed_seconds": round(elapsed, 2),
            }
        )
        print(
            json.dumps(
                {
                    "track": track_name,
                    "segments": len(segments),
                    "elapsed_seconds": round(elapsed, 2),
                    "raw_json": raw_json.name,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    manifest_path = args.cache_dir / f"unit{args.unit}_{slug}_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "tracks": len(manifest),
                "manifest": str(manifest_path.relative_to(ROOT)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
