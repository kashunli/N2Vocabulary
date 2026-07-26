#!/usr/bin/env python3
"""Corroborate ASR review candidates against raw OCR text.

This stage is deliberately conservative: agreement between audio ASR and raw
OCR is strong evidence that structured/canonical text drifted during parsing,
but it still produces a review list rather than editing the database.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from audit_vocabulary_audio import phonetic_hiragana


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_AUDIT = ROOT / "work" / "vocabulary_audio_audit" / "n2_all_both" / "audit.json"
DEFAULT_SOURCE = ROOT / "json"
PUNCTUATION_RE = re.compile(r"[\s「」『』（）()［］\[\]{}<>【】・…。.，、／/!！?？:：;；~〜]")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare reviewed ASR sentences with raw OCR page text."
    )
    parser.add_argument("--audit-json", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--asr-raw-threshold", type=float, default=0.90)
    parser.add_argument("--margin-threshold", type=float, default=0.04)
    return parser


def normalize(text: str) -> str:
    return phonetic_hiragana(text)


def similarity(left: str, right: str) -> float:
    left_norm, right_norm = normalize(left), normalize(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0
    if left_norm in right_norm:
        return len(left_norm) / len(right_norm)
    if right_norm in left_norm:
        return len(right_norm) / len(left_norm)
    return SequenceMatcher(None, left_norm, right_norm).ratio()


def load_raw_blocks(source_dir: Path) -> dict[int, dict[str, str]]:
    blocks: dict[int, dict[str, str]] = {}
    for path in sorted(source_dir.glob("page_*.json")):
        page = json.loads(path.read_text(encoding="utf-8"))
        raw_text = page.get("raw_text", "")
        for entry in page.get("entries", []):
            number = entry.get("number")
            if not isinstance(number, int):
                continue
            match = re.search(
                rf"(?ms)^{number}\s.*?(?=^\d{{1,4}}\s|\Z)",
                raw_text,
            )
            if match:
                blocks[number] = {"page": path.name, "block": match.group(0)}
    return blocks


def best_line(block: str, reference: str) -> tuple[float, str]:
    lines: list[str] = []
    for raw_line in block.splitlines()[1:]:
        for segment in re.split(r"\s*・\s*", raw_line):
            cleaned = segment.strip(" ・-①②③④⑤⑥⑦⑧⑨⑩")
            if cleaned:
                lines.append(cleaned)
    if not lines:
        return 0.0, ""
    return max((similarity(line, reference), line) for line in lines)


def build_evidence(
    audit: dict[str, Any],
    blocks: dict[int, dict[str, str]],
    asr_raw_threshold: float,
    margin_threshold: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in audit["items"]:
        comparison = item["comparisons"].get("sentence")
        if not comparison or comparison["status"] == "pass":
            continue
        source_index = int(item["source_index"])
        source = blocks.get(source_index)
        if source is None:
            continue
        asr_score, raw_line = best_line(source["block"], comparison["transcript"])
        db_score, _ = best_line(source["block"], comparison["expected"])
        margin = asr_score - db_score
        if asr_score >= asr_raw_threshold and margin >= margin_threshold:
            classification = "source_confirmed"
        elif db_score >= 0.96 and db_score >= asr_score + margin_threshold:
            classification = "source_supports_db"
        else:
            classification = "ambiguous"
        rows.append(
            {
                "source_index": source_index,
                "unit": item["unit_number"],
                "headword": item["headword"],
                "classification": classification,
                "audit_score": comparison["score"],
                "asr_vs_raw": round(asr_score, 4),
                "db_vs_raw": round(db_score, 4),
                "evidence_margin": round(margin, 4),
                "expected": comparison["expected"],
                "transcript": comparison["transcript"],
                "raw_line": raw_line,
                "raw_page": source["page"],
                "audio_clip": comparison["audio_clip"],
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            0 if row["classification"] == "source_confirmed" else 1,
            -row["evidence_margin"],
            row["source_index"],
        ),
    )


def write_outputs(output_dir: Path, rows: list[dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else [
        "source_index", "unit", "headword", "classification", "audit_score",
        "asr_vs_raw", "db_vs_raw", "evidence_margin", "expected", "transcript",
        "raw_line", "raw_page", "audio_clip",
    ]
    with (output_dir / "source_evidence.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (output_dir / "source_evidence.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    confirmed = [row for row in rows if row["classification"] == "source_confirmed"]
    lines = [
        "# Source-confirmed vocabulary/audio mismatches",
        "",
        f"- Sentence review candidates checked: `{len(rows)}`",
        f"- ASR and raw OCR favor a correction: `{len(confirmed)}`",
        "",
        "These are correction candidates, not automatic database edits.",
        "",
    ]
    for row in confirmed:
        lines.extend(
            [
                f"## #{row['source_index']} · Unit {row['unit']} · {row['headword']}",
                "",
                f"- Canonical: {row['expected']}",
                f"- ASR: {row['transcript']}",
                f"- Raw OCR: {row['raw_line']}",
                f"- Evidence: ASR/raw `{row['asr_vs_raw']}`, DB/raw `{row['db_vs_raw']}`",
                f"- Inputs: `{row['raw_page']}`, `{row['audio_clip']}`",
                "",
            ]
        )
    (output_dir / "source_confirmed.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = build_parser().parse_args()
    audit = json.loads(args.audit_json.read_text(encoding="utf-8"))
    blocks = load_raw_blocks(args.source_dir)
    rows = build_evidence(
        audit, blocks, args.asr_raw_threshold, args.margin_threshold
    )
    output_dir = args.output_dir or args.audit_json.parent
    write_outputs(output_dir, rows)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1
    print(json.dumps({"reviewed": len(rows), **counts}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
