#!/usr/bin/env python3
"""Validate and normalize exported human decisions for the N2 audio audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EVIDENCE = (
    ROOT / "work" / "vocabulary_audio_audit" / "n2_all_both" / "source_evidence.json"
)
DEFAULT_OUTPUT = ROOT / "reviews" / "vocabulary_audio" / "n2_all_both.json"
ALLOWED_DECISIONS = {"replace", "keep", "custom", "audio_problem"}
REQUIRED_FIELDS = {
    "source_index",
    "unit",
    "headword",
    "decision",
    "original_text",
    "replacement_text",
    "audio_clip",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a reviewer JSON export against its signed evidence source."
    )
    parser.add_argument("review_json", type=Path)
    parser.add_argument("--evidence-json", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--audio-problem",
        type=int,
        action="append",
        default=[],
        metavar="SOURCE_INDEX",
        help="Reclassify a reviewed row when the sentence clip contains word audio.",
    )
    return parser


def comparable_text(value: Any) -> str:
    # Formatting-only differences are not a meaningful replacement decision.
    return re.sub(r"[\s、。！？!?「」『』（）()［］\[\]・…〜～,./]", "", str(value or ""))


def append_note(existing: Any, message: str) -> str:
    note = str(existing or "").strip()
    return f"{note} {message}".strip() if note else message


def validate_and_normalize(
    review: dict[str, Any],
    evidence_rows: list[dict[str, Any]],
    evidence_sha256: str,
    audio_problem_indices: set[int],
) -> tuple[dict[str, Any], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    normalized_noops: list[int] = []
    applied_audio_problems: list[int] = []

    if review.get("version") != 1:
        errors.append(f"unsupported review version: {review.get('version')!r}")
    if review.get("source_sha256") != evidence_sha256:
        errors.append("source_sha256 does not match the current evidence JSON")

    evidence_by_id: dict[int, dict[str, Any]] = {}
    for row in evidence_rows:
        source_index = int(row["source_index"])
        if source_index in evidence_by_id:
            errors.append(f"duplicate evidence source_index: {source_index}")
        evidence_by_id[source_index] = row

    raw_decisions = review.get("decisions")
    if not isinstance(raw_decisions, list):
        errors.append("decisions must be a list")
        raw_decisions = []

    seen: set[int] = set()
    decisions: list[dict[str, Any]] = []
    normalized_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    for position, raw in enumerate(raw_decisions):
        if not isinstance(raw, dict):
            errors.append(f"decision {position} is not an object")
            continue
        missing_fields = sorted(REQUIRED_FIELDS - raw.keys())
        if missing_fields:
            errors.append(f"decision {position} is missing fields: {', '.join(missing_fields)}")
            continue

        try:
            source_index = int(raw["source_index"])
        except (TypeError, ValueError):
            errors.append(f"decision {position} has an invalid source_index")
            continue
        if source_index in seen:
            errors.append(f"duplicate decision source_index: {source_index}")
            continue
        seen.add(source_index)

        evidence = evidence_by_id.get(source_index)
        if evidence is None:
            errors.append(f"decision source_index {source_index} is absent from evidence")
            continue
        decision = dict(raw)
        kind = str(decision.get("decision", ""))
        if kind not in ALLOWED_DECISIONS:
            errors.append(f"source_index {source_index} has invalid decision: {kind!r}")
        if decision.get("original_text") != evidence.get("expected"):
            errors.append(f"source_index {source_index} original_text is stale")
        if decision.get("audio_clip") != evidence.get("audio_clip"):
            errors.append(f"source_index {source_index} audio_clip does not match evidence")
        audio_path = ROOT / str(evidence.get("audio_clip", ""))
        if not audio_path.is_file():
            errors.append(f"source_index {source_index} audio file is missing: {audio_path}")

        replacement = str(decision.get("replacement_text", "")).strip()
        if kind in {"replace", "custom"} and not replacement:
            errors.append(f"source_index {source_index} has an empty replacement")
        if kind == "replace" and comparable_text(replacement) == comparable_text(
            decision.get("original_text")
        ):
            decision["decision"] = "keep"
            decision["replacement_text"] = decision["original_text"]
            decision["note"] = append_note(
                decision.get("note"), "Normalized from a no-op replacement."
            )
            decision["updated_at"] = normalized_at
            normalized_noops.append(source_index)

        if source_index in audio_problem_indices:
            decision["decision"] = "audio_problem"
            decision["replacement_text"] = decision["original_text"]
            decision["note"] = append_note(
                decision.get("note"),
                "Sentence clip contains the vocabulary-word audio before the example sentence.",
            )
            decision["updated_at"] = normalized_at
            applied_audio_problems.append(source_index)

        decisions.append(decision)

    unknown_overrides = sorted(audio_problem_indices - seen)
    if unknown_overrides:
        errors.append(
            "audio-problem overrides are not present in the review: "
            + ", ".join(map(str, unknown_overrides))
        )

    undecided = sorted(set(evidence_by_id) - seen)
    if undecided:
        warnings.append(f"{len(undecided)} evidence row(s) remain undecided")

    if errors:
        raise ValueError("\n".join(errors))

    decisions.sort(key=lambda row: int(row["source_index"]))
    counts = Counter(str(row["decision"]) for row in decisions)
    result = {
        "version": 1,
        "source_sha256": evidence_sha256,
        "exported_at": review.get("exported_at"),
        "validated_at": normalized_at,
        "decisions": decisions,
        "validation": {
            "status": "valid_incomplete" if undecided else "valid_complete",
            "decision_count": len(decisions),
            "evidence_count": len(evidence_rows),
            "decision_counts": dict(sorted(counts.items())),
            "normalized_noop_replacements": normalized_noops,
            "audio_problem_overrides": applied_audio_problems,
            "undecided_source_indices": undecided,
            "warnings": warnings,
        },
    }
    return result, result["validation"]


def main() -> int:
    args = build_parser().parse_args()
    evidence_bytes = args.evidence_json.read_bytes()
    evidence_rows = json.loads(evidence_bytes.decode("utf-8"))
    review = json.loads(args.review_json.read_text(encoding="utf-8"))
    if not isinstance(evidence_rows, list):
        raise ValueError("evidence JSON must contain a list")
    if not isinstance(review, dict):
        raise ValueError("review JSON must contain an object")

    normalized, report = validate_and_normalize(
        review,
        evidence_rows,
        hashlib.sha256(evidence_bytes).hexdigest(),
        set(args.audio_problem),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output": str(args.output), **report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
