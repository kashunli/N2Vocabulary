#!/usr/bin/env python3
"""Step 1: Produce output/vocabulary_db.json — the clean, human-editable database.

Usage:
    python -u parse/scripts/make_clean_db.py [--out output/vocabulary_db.json]

What it does:
- Strips all alignment metadata (timestamps, confidence, transcripts)
- Keeps only learning-relevant fields + resolved clip paths
- Adds explanation: null placeholder for later filling
- Resolves clip paths from disk (handles -deduced variants)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def resolve_clips(idx: int, unit: int, clips_root: Path) -> tuple[str | None, str | None]:
    d = clips_root / f"unit{unit:02d}"

    def first(names):
        for n in names:
            p = d / n
            if p.exists():
                return str(p.relative_to(ROOT)).replace("\\", "/")
        return None

    word = first([f"word{idx}.mp3", f"word{idx}-deduced.mp3"])
    sent = first([f"sentence{idx}.mp3", f"sentence{idx}-deduced.mp3"])
    return word, sent


def clean_entry(e: dict, clips_root: Path) -> dict:
    idx      = e["index"]
    unit_num = e["unit"]["number"]
    examples = e.get("examples_all") or []
    sentence = examples[0] if examples else e.get("sentence_text") or ""
    more     = examples[1:] if len(examples) > 1 else []

    word_clip, sent_clip = resolve_clips(idx, unit_num, clips_root)

    return {
        "index":        idx,
        "unit":         {"number": unit_num, "header": e["unit"].get("header", "")},
        "reading":      e.get("reading") or "",
        "kanji":        e.get("kanji") or "",
        "headword_text": e.get("headword_text") or "",
        "verb_pattern": e.get("verb_pattern") or None,
        "meaning_en":   (e.get("meanings") or {}).get("en") or "",
        "meaning_zh":   (e.get("meanings") or {}).get("zh") or "",
        "sentence":     sentence,
        "examples":     more,
        "word_clip":    word_clip,
        "sentence_clip": sent_clip,
        "explanation":  e.get("explanation") or None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="output/vocabulary_combined.json")
    ap.add_argument("--out", default="output/vocabulary_db.json")
    ap.add_argument("--clips", default="output/clips")
    args = ap.parse_args()

    src_path   = ROOT / args.src
    out_path   = ROOT / args.out
    clips_root = ROOT / args.clips

    raw = json.loads(src_path.read_text(encoding="utf-8"))
    raw.sort(key=lambda e: e["index"])

    db = [clean_entry(e, clips_root) for e in raw]

    no_word = sum(1 for e in db if not e["word_clip"])
    no_sent = sum(1 for e in db if not e["sentence_clip"])

    out_path.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Written {out_path}  ({len(db)} entries)")
    print(f"  No word clip    : {no_word}")
    print(f"  No sentence clip: {no_sent}")


if __name__ == "__main__":
    main()
