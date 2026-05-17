#!/usr/bin/env python3
"""Generate N2Words.apkg - Anki deck for all N2 vocabulary entries.

Usage:
    python -u skills/makeAnkiCards/scripts/make_anki.py [--out output/N2Words.apkg]

Reads the current project-level vocabulary.json and packages clips from clips/.
Stable deck/model/note IDs are preserved so Anki can update existing notes.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import html as html_mod

import genanki

ROOT = Path(__file__).resolve().parents[3]

# ── IDs (stable — do not change once deck exists) ─────────────────────────────
DECK_ID   = 1_234_567_890
MODEL_ID  = 9_876_543_210

# ── Unit colour palette (hue per unit, consistent saturation/lightness) ───────
UNIT_COLORS = {
    1:  "#5b9bd5",  # blue
    2:  "#e07b54",  # orange
    3:  "#56b45d",  # green
    4:  "#9b6bbf",  # purple
    5:  "#d4a017",  # gold
    6:  "#3ab0b0",  # teal
    7:  "#c2564b",  # red
    8:  "#4a8fa8",  # steel blue
    9:  "#8b6e45",  # brown
    10: "#d16b9e",  # pink
    11: "#6aaa6a",  # lime green
    12: "#7060a0",  # indigo
    13: "#a07050",  # sienna
}

# ── Template ──────────────────────────────────────────────────────────────────

FRONT_TMPL = """\
<div class="card-front">
  <div class="unit-badge" style="background:{{UnitColor}}">{{UnitLabel}}</div>
  <div class="headword-block">
    <span class="headword">{{Headword}}</span>
    {{#VerbPattern}}<span class="verb-pattern">({{VerbPattern}})</span>{{/VerbPattern}}
  </div>
  <div class="reading">{{Reading}}</div>
  <div class="audio-row">{{WordAudio}}</div>
</div>
"""

BACK_TMPL = """\
<div class="card-back">
  <div class="unit-badge" style="background:{{UnitColor}}">{{UnitLabel}}</div>
  <div class="headword-block">
    <span class="headword">{{Headword}}</span>
    {{#VerbPattern}}<span class="verb-pattern">({{VerbPattern}})</span>{{/VerbPattern}}
  </div>
  <div class="reading">{{Reading}}</div>
  <div class="audio-row">{{WordAudio}}</div>

  <hr class="divider">

  <div class="meanings">
    {{#MeaningEN}}<div class="meaning en"><span class="lang-tag">EN</span> {{MeaningEN}}</div>{{/MeaningEN}}
    {{#MeaningZH}}<div class="meaning zh"><span class="lang-tag">中</span> {{MeaningZH}}</div>{{/MeaningZH}}
    {{#MeaningKO}}<div class="meaning ko"><span class="lang-tag">한</span> {{MeaningKO}}</div>{{/MeaningKO}}
  </div>

  <hr class="divider">

  <div class="sentence-block">
    <div class="audio-row">{{SentenceAudio}}</div>
    <div class="sentence">{{Sentence}}</div>
  </div>

  {{#MoreExamples}}
  <div class="more-examples">
    <div class="examples-list">{{MoreExamples}}</div>
  </div>
  {{/MoreExamples}}

  <div class="index-tag">#{{Index}}</div>
</div>
"""

CSS = """\
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;600;700&family=Inter:wght@400;500;600&display=swap');

:root {
  --bg: #1e1e2e;
  --surface: #282840;
  --surface2: #313150;
  --text: #cdd6f4;
  --text-dim: #7f849c;
  --accent: #89b4fa;
  --divider: #45475a;
  --radius: 10px;
}

.card, body {
  font-family: 'Inter', 'Noto Sans JP', sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  margin: 0;
  padding: 0;
}

.card-front, .card-back {
  max-width: 560px;
  margin: 0 auto;
  padding: 28px 24px 36px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
  min-height: 100vh;
  box-sizing: border-box;
}

/* Unit badge */
.unit-badge {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #fff;
  padding: 3px 10px;
  border-radius: 20px;
  opacity: 0.9;
  margin-bottom: 4px;
}

/* Headword */
.headword-block {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}

.headword {
  font-family: 'Noto Sans JP', sans-serif;
  font-size: 46px;
  font-weight: 700;
  line-height: 1.1;
  color: #fff;
  letter-spacing: -0.01em;
}

.verb-pattern {
  font-size: 15px;
  color: var(--text-dim);
  font-style: italic;
}

/* Reading */
.reading {
  font-family: 'Noto Sans JP', sans-serif;
  font-size: 20px;
  color: var(--accent);
  letter-spacing: 0.05em;
  margin-top: -4px;
}

/* Anki native audio replay button */
.audio-row {
  margin: 4px 0;
}

.replay-button svg { fill: var(--accent); }
.replay-button { opacity: 0.85; }
.replay-button:hover { opacity: 1; }

/* Divider */
hr.divider {
  border: none;
  border-top: 1px solid var(--divider);
  width: 100%;
  margin: 6px 0;
}

/* Meanings */
.meanings {
  display: flex;
  flex-direction: column;
  gap: 5px;
  width: 100%;
}

.meaning {
  font-size: 15px;
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.lang-tag {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  background: var(--surface2);
  color: var(--text-dim);
  padding: 1px 6px;
  border-radius: 4px;
  min-width: 22px;
  text-align: center;
}

/* Sentence block */
.sentence-block {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sentence {
  font-family: 'Noto Sans JP', sans-serif;
  font-size: 19px;
  line-height: 1.6;
  color: #e0e6f0;
  padding: 10px 14px;
  background: var(--surface);
  border-radius: var(--radius);
  border-left: 3px solid var(--accent);
}

/* More examples */
.more-examples {
  width: 100%;
  margin-top: 4px;
}

.examples-list {
  font-family: 'Noto Sans JP', sans-serif;
  font-size: 15px;
  line-height: 1.8;
  color: #b0b8d0;
  padding: 6px 12px;
  border-left: 2px solid var(--divider);
}

.examples-list p {
  margin: 0 0 4px 0;
}

/* Index tag */
.index-tag {
  font-size: 11px;
  color: var(--text-dim);
  margin-top: auto;
  padding-top: 16px;
  align-self: flex-end;
}

/* index tag */
"""


def _resolve_declared_clip(entry: dict, field: str) -> Path | None:
    clip = entry.get(field)
    if not clip:
        return None
    p = Path(clip)
    if not p.is_absolute():
        p = ROOT / p
    return p if p.exists() else None


def _find_clip_by_name(clips_root: Path, idx: int, kind: str) -> Path | None:
    for name in (f"{kind}{idx:03d}.mp3", f"{kind}{idx}.mp3", f"{kind}{idx:03d}-deduced.mp3", f"{kind}{idx}-deduced.mp3"):
        matches = sorted(clips_root.rglob(name))
        if matches:
            return matches[0]
    return None


def resolve_clips(entry: dict, clips_root: Path) -> tuple[Path | None, Path | None]:
    """Find word and sentence clip paths on disk for an entry.

    Trusts explicit vocabulary.json clip paths first, then searches by filename.
    Returns (word_path, sentence_path) as absolute Paths or None.
    """
    idx = entry["index"]
    word = _resolve_declared_clip(entry, "word_clip") or _find_clip_by_name(clips_root, idx, "word")
    sent = _resolve_declared_clip(entry, "sentence_clip") or _find_clip_by_name(clips_root, idx, "sentence")
    return word, sent


def build_notes(data: list[dict], clips_root: Path) -> tuple[list[genanki.Note], list[Path]]:
    """Build genanki notes and collect media file paths."""
    notes: list[genanki.Note] = []
    media:  list[Path]        = []
    media_set: set[Path]      = set()

    model = genanki.Model(
        MODEL_ID,
        "N2 Vocabulary",
        fields=[
            {"name": "Index"},
            {"name": "UnitLabel"},
            {"name": "UnitColor"},
            {"name": "Headword"},
            {"name": "Reading"},
            {"name": "VerbPattern"},
            {"name": "MeaningEN"},
            {"name": "MeaningZH"},
            {"name": "MeaningKO"},
            {"name": "WordAudio"},
            {"name": "Sentence"},
            {"name": "SentenceAudio"},
            {"name": "MoreExamples"},
        ],
        templates=[
            {
                "name": "N2 Vocabulary Card",
                "qfmt": FRONT_TMPL,
                "afmt": BACK_TMPL,
            }
        ],
        css=CSS,
    )

    for e in data:
        idx        = e["index"]
        unit_num   = e["unit"]["number"]
        unit_hdr   = e["unit"].get("header", f"Unit {unit_num:02d}")
        unit_label = unit_hdr.replace("Unit ", "U").split(" ")[0] + " " + " ".join(unit_hdr.split(" ")[2:]) if " " in unit_hdr else unit_hdr
        unit_color = UNIT_COLORS.get(unit_num, "#666")

        word_p, sent_p = resolve_clips(e, clips_root)

        def media_tag(path: Path | None, label: str) -> str:
            if path is None:
                return ""
            if path not in media_set:
                media_set.add(path)
                media.append(path)
            return f"[sound:{path.name}]"

        word_audio = media_tag(word_p, "word")
        sent_audio = media_tag(sent_p, "sent")

        def t(v) -> str:
            """Ensure string and HTML-escape angle brackets in plain text."""
            s = v or ""
            return html_mod.escape(str(s))

        examples_all = e.get("examples_all") or e.get("examples") or []
        sentence     = e.get("sentence") or e.get("sentence_text") or (examples_all[0] if examples_all else "")
        more_html    = "".join(f"<p>{html_mod.escape(ex)}</p>" for ex in examples_all)

        note = genanki.Note(
            model=model,
            fields=[
                str(idx),
                unit_label,
                unit_color,
                t(e.get("headword_text")),
                t(e.get("reading")),
                t(e.get("verb_pattern")),
                t(e.get("meaning_en", "")),
                t(e.get("meaning_zh", "")),
                t(e.get("meaning_ko", "")),
                word_audio,
                t(sentence),
                sent_audio,
                more_html,
            ],
            guid=genanki.guid_for(f"n2vocab_{idx}"),
            tags=[f"unit{unit_num:02d}", f"N2"],
        )
        notes.append(note)

    return notes, media, model


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate N2Words.apkg")
    ap.add_argument("--out", default="output/N2Words.apkg")
    ap.add_argument("--vocab", default="vocabulary.json")
    ap.add_argument("--clips", default="clips")
    args = ap.parse_args()

    clips_root = ROOT / args.clips
    data = json.loads((ROOT / args.vocab).read_text(encoding="utf-8"))
    data.sort(key=lambda e: e["index"])

    print(f"Building notes for {len(data)} entries…")
    notes, media, model = build_notes(data, clips_root)

    deck = genanki.Deck(DECK_ID, "N2Words")
    for note in notes:
        deck.add_note(note)

    package = genanki.Package(deck)
    package.media_files = [str(p) for p in media]

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    package.write_to_file(str(out))

    no_word = sum(1 for e in data if resolve_clips(e, clips_root)[0] is None)
    no_sent = sum(1 for e in data if resolve_clips(e, clips_root)[1] is None)
    print(f"Written: {out}  ({out.stat().st_size // 1024 // 1024} MB)")
    print(f"  Notes    : {len(notes)}")
    print(f"  Media    : {len(media)} files")
    print(f"  No word audio  : {no_word}")
    print(f"  No sentence audio: {no_sent}")


if __name__ == "__main__":
    main()
