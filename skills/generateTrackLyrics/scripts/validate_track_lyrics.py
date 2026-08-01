#!/usr/bin/env python3
"""Revalidate generated manifests, views, and immutable source fingerprints."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from formats import safe_track_name, source_fingerprint, validate_cues
from model import Cue


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def audio_duration(path: str) -> float:
    """Read the immutable track duration without decoding it into memory."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def validate_book(book_dir: Path) -> dict:
    manifest_path = book_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cues = [Cue(**row) for row in manifest["cues"]]
    report = validate_cues(cues, manifest["expected_counts"], 0.75)

    fingerprint_errors = []
    for path, expected in manifest["source_fingerprints"].items():
        actual = source_fingerprint(path)
        if actual != expected:
            fingerprint_errors.append({"source_audio": path, "expected": expected, "actual": actual})

    view_errors = []
    expected_views: set[str] = set()
    for track in {cue.track for cue in cues}:
        stem = safe_track_name(track)
        for suffix in (".lrc", ".vtt"):
            path = book_dir / "tracks" / f"{stem}{suffix}"
            expected_views.add(path.relative_to(book_dir).as_posix())
            if not path.is_file() or path.stat().st_size == 0:
                view_errors.append({"reason": "missing_or_empty_view", "path": str(path)})

    # Exact-set validation catches stale lyric files left from a previous run.
    actual_views = {
        path.relative_to(book_dir).as_posix()
        for suffix in ("*.lrc", "*.vtt")
        for path in (book_dir / "tracks").glob(suffix)
    }
    for path in sorted(actual_views - expected_views):
        view_errors.append({"reason": "unexpected_view", "path": path})
    if set(manifest.get("generated_files", [])) != expected_views:
        view_errors.append(
            {
                "reason": "manifest_view_set_mismatch",
                "expected": sorted(expected_views),
                "actual": sorted(manifest.get("generated_files", [])),
            }
        )

    bound_errors = []
    duration_by_source = {
        source: audio_duration(source) for source in manifest["source_fingerprints"]
    }
    for cue in cues:
        duration = duration_by_source[cue.source_audio]
        # Allow one video-frame-equivalent of metadata/decoder rounding.
        if cue.end > duration + 0.04:
            bound_errors.append(
                {
                    "reason": "cue_exceeds_track",
                    "entry_id": cue.entry_id,
                    "kind": cue.kind,
                    "end": cue.end,
                    "track_duration": duration,
                    "source_audio": cue.source_audio,
                }
            )

    unresolved_items = manifest.get("unresolved_items", [])
    review_count = sum(bool(cue.review_reasons) for cue in cues) + len(unresolved_items)
    expected_review = [cue.to_dict() for cue in cues if cue.review_reasons] + unresolved_items
    review_path = book_dir / "review_queue.json"
    actual_review = json.loads(review_path.read_text(encoding="utf-8")) if review_path.is_file() else None
    review_errors = []
    expected_review_rows = sorted(
        json.dumps(row, ensure_ascii=False, sort_keys=True) for row in expected_review
    )
    actual_review_rows = (
        sorted(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in actual_review)
        if isinstance(actual_review, list)
        else None
    )
    if actual_review_rows != expected_review_rows:
        review_errors.append(
            {
                "reason": "review_queue_mismatch",
                "expected_count": len(expected_review),
                "actual_count": len(actual_review) if isinstance(actual_review, list) else None,
            }
        )
    report.update(
        {
            "fingerprint_error_count": len(fingerprint_errors),
            "fingerprint_errors": fingerprint_errors,
            "view_error_count": len(view_errors),
            "view_errors": view_errors,
            "bound_error_count": len(bound_errors),
            "bound_errors": bound_errors,
            "review_count": review_count,
            "unresolved_item_count": len(unresolved_items),
            "review_queue_error_count": len(review_errors),
            "review_queue_errors": review_errors,
        }
    )
    report["error_count"] += (
        len(fingerprint_errors) + len(view_errors) + len(bound_errors) + len(review_errors)
    )
    report["status"] = "accepted" if report["error_count"] == 0 and review_count == 0 else "needs_review"
    (book_dir / "validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book", choices=("n1", "n2", "n3", "all"), required=True)
    parser.add_argument("--output-root", type=Path, default=None)
    args = parser.parse_args()
    output_root = args.output_root or repo_root() / "output" / "track_lyrics"
    books = ("n1", "n2", "n3") if args.book == "all" else (args.book,)
    failed = False
    for book in books:
        report = validate_book(output_root / book)
        print(f"{book.upper()}: {report['status']} ({report['error_count']} errors, {report['review_count']} review cues)")
        failed = failed or report["error_count"] > 0
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
