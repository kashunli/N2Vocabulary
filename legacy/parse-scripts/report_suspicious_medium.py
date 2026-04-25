#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from align import detect_silence_boundaries, transcribe_full_track, load_backend

ROOT = Path(__file__).resolve().parents[2]
FLAGS_PATH = ROOT / "output" / "needs_human_mapping_fix.json"
CACHE_DIR = ROOT / "output" / "whisper_cache"
REPORT_JSON = ROOT / "output" / "medium_suspicious_report.json"
REPORT_MD = ROOT / "output" / "medium_suspicious_report.md"


def track_number(track_name: str) -> str:
    return track_name.split()[0]


def track_spec(unit: int, track_name: str) -> dict[str, Path | str | int]:
    num = track_number(track_name)
    folder = "Unit1 名詞A" if unit == 1 else "Unit2 動詞A"
    return {
        "unit": unit,
        "track_name": track_name,
        "track_rel": f"audio/{folder}/{track_name}",
        "entries_rel": f"output/unit{unit}_entries/entries_{num}.json",
        "mapping_rel": f"output/unit{unit}_mappings/mapping_{num}.json",
        "review_rel": (
            "output/review_unit1_combined.json"
            if unit == 1
            else "output/review_unit2_all.json"
        ),
        "cache_base": CACHE_DIR / f"unit{unit}_track_{num}_base.json",
        "cache_medium": CACHE_DIR / f"unit{unit}_track_{num}_medium.json",
    }


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def overlaps(seg: dict, start: float, end: float) -> bool:
    return seg["end"] >= start and seg["start"] <= end


def format_segments_md(segments: list[dict]) -> list[str]:
    if not segments:
        return ["- none"]
    return [
        f"- `{seg['start']:.3f}-{seg['end']:.3f}` {seg['text']}"
        for seg in segments
    ]


def format_boundaries_md(boundaries: list[tuple[float, str]]) -> list[str]:
    if not boundaries:
        return ["- none"]
    return [f"- `{t:.3f}` silence_{typ}" for t, typ in boundaries]


def format_regions_md(regions: list[tuple[float, float]]) -> list[str]:
    if not regions:
        return ["- none"]
    return [f"- `{start:.3f}-{end:.3f}` ({end - start:.3f}s)" for start, end in regions]


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Transcribe the suspicious tracks with Whisper medium and "
                    "write a comparison report for the flagged entries."
    )
    ap.add_argument(
        "--also-base",
        action="store_true",
        help="Also generate fresh base caches for side-by-side comparison.",
    )
    ap.add_argument(
        "--device",
        default="cpu",
        help="Whisper device for openai backend (default: cpu).",
    )
    args = ap.parse_args()

    flags = read_json(FLAGS_PATH)
    by_track: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for item in flags:
        by_track[(item["unit"], item["track"])].append(item)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    report_items: list[dict] = []
    md_lines = [
        "# Medium Whisper suspicious-entry report",
        "",
        "This report compares the current base-derived mapping JSON against a fresh `medium` transcription.",
        "",
    ]

    medium_backend = load_backend("openai", model_name="medium", device=args.device)
    base_backend = None
    if args.also_base:
        base_backend = load_backend("openai", model_name="base", device=args.device)

    for (unit, track_name), flagged in sorted(by_track.items()):
        spec = track_spec(unit, track_name)
        track_path = ROOT / spec["track_rel"]
        mapping_path = ROOT / spec["mapping_rel"]
        entries_path = ROOT / spec["entries_rel"]

        print(f"Transcribing medium: Unit {unit} / {track_name}", flush=True)
        medium_segments = transcribe_full_track(track_path, backend=medium_backend)
        spec["cache_medium"].write_text(
            json.dumps(medium_segments, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        base_segments = None
        if args.also_base:
            print(f"Transcribing base: Unit {unit} / {track_name}", flush=True)
            base_segments = transcribe_full_track(track_path, backend=base_backend)
            spec["cache_base"].write_text(
                json.dumps(base_segments, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        mapping = {item["index"]: item for item in read_json(mapping_path)}
        entries = {item["index"]: item for item in read_json(entries_path)}
        boundaries, _ = detect_silence_boundaries(track_path)

        md_lines.extend([
            f"## Unit {unit} / {track_name}",
            "",
            f"- Medium cache: `{spec['cache_medium'].relative_to(ROOT)}`",
        ])
        if args.also_base:
            md_lines.append(f"- Base cache: `{spec['cache_base'].relative_to(ROOT)}`")
        md_lines.append("")

        for flag in sorted(flagged, key=lambda item: (item["index"], item["kind"])):
            idx = flag["index"]
            entry = entries[idx]
            current = mapping[idx]
            word = current.get("word")
            sentence = current.get("sentence")
            starts = [part["start"] for part in (word, sentence) if part]
            ends = [part["end"] for part in (word, sentence) if part]
            window_start = max(0.0, min(starts) - 1.0)
            window_end = max(ends) + 1.0

            medium_window = [seg for seg in medium_segments if overlaps(seg, window_start, window_end)]
            base_window = None
            if base_segments is not None:
                base_window = [seg for seg in base_segments if overlaps(seg, window_start, window_end)]

            local_boundaries = [
                (t, typ)
                for t, typ in boundaries
                if window_start <= t <= window_end
            ]
            local_regions = []
            last_end = window_start
            for t, typ in local_boundaries:
                if typ == "end":
                    last_end = t
                elif typ == "start" and t > last_end:
                    local_regions.append((last_end, t))

            item = {
                "unit": unit,
                "track": track_name,
                "index": idx,
                "kind": flag["kind"],
                "entry": entry,
                "current_mapping": current,
                "flag": flag,
                "window": [round(window_start, 3), round(window_end, 3)],
                "medium_segments": medium_window,
                "silence_boundaries": [
                    {"time": round(t, 3), "type": typ}
                    for t, typ in local_boundaries
                ],
                "speech_regions": [
                    {"start": round(start, 3), "end": round(end, 3), "duration": round(end - start, 3)}
                    for start, end in local_regions
                ],
            }
            if base_window is not None:
                item["base_segments"] = base_window
            report_items.append(item)

            md_lines.extend([
                f"### {idx} {entry['headword']} ({flag['kind']})",
                "",
                f"- Expected reading: `{entry.get('reading', '')}`",
                f"- Expected sentence: {entry.get('sentence', '')}",
                f"- Current mapping word: `{word['start']:.3f}-{word['end']:.3f}`" if word else "- Current mapping word: none",
                f"- Current mapping sentence: `{sentence['start']:.3f}-{sentence['end']:.3f}`" if sentence else "- Current mapping sentence: none",
                f"- Review flag suggested cut: `{flag['new'][0]:.3f}-{flag['new'][1]:.3f}`",
                f"- Inspection window: `{window_start:.3f}-{window_end:.3f}`",
                "",
                "Medium segments:",
                *format_segments_md(medium_window),
                "",
            ])
            if base_window is not None:
                md_lines.extend([
                    "Base segments:",
                    *format_segments_md(base_window),
                    "",
                ])
            md_lines.extend([
                "Speech regions from silence boundaries:",
                *format_regions_md(local_regions),
                "",
                "Silence boundaries:",
                *format_boundaries_md(local_boundaries),
                "",
            ])

    REPORT_JSON.write_text(
        json.dumps(report_items, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    REPORT_MD.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT_JSON.relative_to(ROOT)}")
    print(f"Wrote {REPORT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
