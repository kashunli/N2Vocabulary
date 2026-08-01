"""Write track-level JSON, LRC, WebVTT, and validation artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from model import Cue


def safe_track_name(track: str) -> str:
    name = re.sub(r"[^0-9A-Za-z._-]+", "_", track).strip("_.")
    return name or "track"


def source_fingerprint(path: str | Path) -> dict:
    resolved = Path(path)
    digest = hashlib.sha256()
    with resolved.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return {"size": resolved.stat().st_size, "sha256": digest.hexdigest()}


def write_book_outputs(
    output_dir: Path,
    *,
    book: str,
    cues: list[Cue],
    expected_counts: dict,
    provenance: dict,
    direct_threshold: float,
    unresolved_items: list[dict] | None = None,
) -> dict:
    unresolved_items = unresolved_items or []
    output_dir.mkdir(parents=True, exist_ok=True)
    tracks_dir = output_dir / "tracks"
    tracks_dir.mkdir(exist_ok=True)

    cues_by_track: dict[str, list[Cue]] = defaultdict(list)
    for cue in sorted(cues, key=lambda item: (item.track, item.start, item.end)):
        cues_by_track[cue.track].append(cue)

    generated_files: list[str] = []
    for track, track_cues in cues_by_track.items():
        stem = safe_track_name(track)
        lrc_path = tracks_dir / f"{stem}.lrc"
        vtt_path = tracks_dir / f"{stem}.vtt"
        lrc_path.write_text(render_lrc(track_cues, book), encoding="utf-8-sig")
        vtt_path.write_text(render_vtt(track_cues), encoding="utf-8")
        # POSIX separators keep manifests stable across Windows and other hosts.
        generated_files.extend(
            [lrc_path.relative_to(output_dir).as_posix(), vtt_path.relative_to(output_dir).as_posix()]
        )

    report = validate_cues(cues, expected_counts, direct_threshold)
    review = [cue.to_dict() for cue in cues if cue.review_reasons] + unresolved_items
    report["review_count"] = len(review)
    report["unresolved_item_count"] = len(unresolved_items)
    report["status"] = "accepted" if report["error_count"] == 0 and not review else "needs_review"

    fingerprints = {
        path: source_fingerprint(path)
        for path in sorted({cue.source_audio for cue in cues})
    }
    manifest = {
        "schema_version": 1,
        "book": book.upper(),
        "status": report["status"],
        "expected_counts": expected_counts,
        "actual_counts": report["actual_counts"],
        "provenance": provenance,
        "source_fingerprints": fingerprints,
        "generated_files": sorted(generated_files),
        "unresolved_items": unresolved_items,
        "cues": [cue.to_dict() for cue in sorted(cues, key=lambda item: (item.track, item.start, item.end))],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "review_queue.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def render_lrc(cues: list[Cue], book: str) -> str:
    lines = [f"[ar:{book.upper()} vocabulary CD]", "[by:N2Vocabulary track-lyrics workflow]"]
    for cue in sorted(cues, key=lambda item: (item.start, item.end)):
        total_centiseconds = max(0, round(cue.start * 100))
        minutes, remainder = divmod(total_centiseconds, 6_000)
        seconds, centiseconds = divmod(remainder, 100)
        lines.append(f"[{minutes:02d}:{seconds:02d}.{centiseconds:02d}]{cue.text}")
    return "\n".join(lines) + "\n"


def render_vtt(cues: list[Cue]) -> str:
    blocks = ["WEBVTT"]
    for cue in sorted(cues, key=lambda item: (item.start, item.end)):
        identifier = f"{cue.entry_id}-{cue.kind}"
        if cue.example_position is not None:
            identifier += f"-{cue.example_position}"
        blocks.append(
            f"{identifier}\n{vtt_time(cue.start)} --> {vtt_time(cue.end)}\n{cue.text}"
        )
    return "\n\n".join(blocks) + "\n"


def vtt_time(seconds: float) -> str:
    millis = max(0, round(seconds * 1_000))
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def validate_cues(cues: list[Cue], expected_counts: dict, direct_threshold: float) -> dict:
    errors: list[dict] = []
    actual = {
        "cue_count": len(cues),
        "word_count": sum(cue.kind == "word" for cue in cues),
        "sentence_count": sum(cue.kind == "sentence" for cue in cues),
        "track_count": len({cue.track for cue in cues}),
    }
    for key, expected in expected_counts.items():
        if key in actual and actual[key] != expected:
            errors.append({"reason": "count_mismatch", "field": key, "expected": expected, "actual": actual[key]})

    by_track: dict[str, list[Cue]] = defaultdict(list)
    for cue in cues:
        if not cue.text.strip():
            errors.append({"reason": "blank_text", "entry_id": cue.entry_id, "kind": cue.kind})
        if cue.start < 0 or cue.end <= cue.start:
            errors.append({"reason": "invalid_bounds", "entry_id": cue.entry_id, "start": cue.start, "end": cue.end})
        if cue.alignment_method == "waveform_correlation" and cue.confidence < direct_threshold:
            errors.append({"reason": "direct_match_below_threshold", "entry_id": cue.entry_id, "kind": cue.kind, "confidence": cue.confidence})
        by_track[cue.track].append(cue)

    for track, track_cues in by_track.items():
        ordered = sorted(track_cues, key=lambda item: (item.start, item.end))
        for previous, current in zip(ordered, ordered[1:]):
            # Safety padding may touch inside a silence, so tolerate 25 ms of
            # encoder rounding but never a meaningful speech overlap.
            if current.start < previous.end - 0.025:
                errors.append(
                    {
                        "reason": "cue_overlap",
                        "track": track,
                        "previous": previous.to_dict(),
                        "current": current.to_dict(),
                    }
                )
    return {"actual_counts": actual, "error_count": len(errors), "errors": errors}
