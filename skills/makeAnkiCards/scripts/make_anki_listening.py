#!/usr/bin/env python3
"""Build output/N2Words_listening.apkg - sentence-listening Anki deck.

Usage:
    python -u skills/makeAnkiCards/scripts/make_anki_listening.py [--out output/N2Words_listening.apkg]

Front: sentence audio auto-plays - pure listening comprehension.
Back:  sentence text + vocabulary headword + meanings + AI explanation.
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import re
from pathlib import Path

import genanki

ROOT = Path(__file__).resolve().parents[3]

# ── Markdown → HTML for explanations ──────────────────────────────────────────

_MD_BOLD = re.compile(r'\*\*(.+?)\*\*')
_MD_ITALIC = re.compile(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)')
_MD_JLPT_TAG = re.compile(r'\[(JLPT\s*N\d+)\]')


def _md_inline(text: str) -> str:
    """Convert inline markdown: **bold**, *italic*, [JLPT N2]."""
    text = _MD_BOLD.sub(r'<strong>\1</strong>', text)
    text = _MD_ITALIC.sub(r'<em>\1</em>', text)
    text = _MD_JLPT_TAG.sub(
        r'<span class="jlpt-tag">\1</span>', text
    )
    return text


def explanation_to_html(text: str) -> str:
    """Convert markdown explanation to HTML for Anki cards."""
    if not text:
        return ""

    sections = text.split("\n---\n")
    rendered_sections = []

    for section in sections:
        lines = section.strip().split("\n")
        items = []
        in_list = False
        current = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- "):
                if not in_list:
                    if current:
                        items.append(("<p>", current))
                        current = []
                    in_list = True
                current.append(stripped[2:])
            else:
                if in_list:
                    items.append(("<ul>", current))
                    current = []
                    in_list = False
                current.append(line)

        if in_list:
            items.append(("<ul>", current))
        elif current:
            items.append(("<p>", current))

        parts = []
        for tag, lines_group in items:
            if tag == "<ul>":
                li_items = "".join(
                    f"<li>{_md_inline(html_mod.escape(li))}</li>" for li in lines_group
                )
                parts.append(f"<ul>{li_items}</ul>")
            elif tag == "<p>":
                for line in lines_group:
                    rendered = _md_inline(html_mod.escape(line))
                    parts.append(rendered)

        rendered_sections.append("\n".join(parts))

    return "\n".join(rendered_sections)

DECK_ID  = 2_345_678_901
MODEL_ID = 8_765_432_109

UNIT_COLORS = {
    1:  "#5b9bd5",
    2:  "#e07b54",
    3:  "#56b45d",
    4:  "#9b6bbf",
    5:  "#d4a017",
    6:  "#3ab0b0",
    7:  "#c2564b",
    8:  "#4a8fa8",
    9:  "#8b6e45",
    10: "#d16b9e",
    11: "#6aaa6a",
    12: "#7060a0",
    13: "#a07050",
}

# ── Templates ─────────────────────────────────────────────────────────────────

FRONT_TMPL = """\
<div class="card-front">
  <div class="unit-badge" style="background:{{UnitColor}}">{{UnitLabel}}</div>
  <div class="prompt-label">Listen · recall the word</div>
  <div class="audio-row">{{SentenceAudio}}</div>
</div>
"""

BACK_TMPL = """\
<div class="card-back">
  <div class="sentence-block">
    <div class="sentence">{{Sentence}}</div>
    <div class="audio-row sentence-replay">{{SentenceAudio}}</div>
  </div>

  <hr class="divider">

  <div class="word-section">
    <div class="unit-badge" style="background:{{UnitColor}}">{{UnitLabel}}</div>
    <div class="headword-block">
      <span class="headword">{{Headword}}</span>
      {{#VerbPattern}}<span class="verb-pattern">({{VerbPattern}})</span>{{/VerbPattern}}
    </div>
    <div class="reading">{{Reading}}</div>
    <div class="audio-row">{{WordAudio}}</div>
    <div class="meanings">
      {{#MeaningEN}}<div class="meaning"><span class="lang-tag">EN</span> {{MeaningEN}}</div>{{/MeaningEN}}
      {{#MeaningZH}}<div class="meaning"><span class="lang-tag">中</span> {{MeaningZH}}</div>{{/MeaningZH}}
    </div>
  </div>

  {{#Explanation}}
  <hr class="divider">
  <div class="explanation">{{Explanation}}</div>
  {{/Explanation}}

  {{#MoreExamples}}
  <hr class="divider">
  <div class="more-examples">
    <div class="more-label">More examples</div>
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
  --accent2: #a6e3a1;
  --divider: #45475a;
  --radius: 10px;
}

.card, body {
  font-family: 'Inter', 'Noto Sans JP', sans-serif;
  background: var(--bg);
  color: var(--text);
  margin: 0;
  padding: 0;
}

.card-front, .card-back {
  max-width: 580px;
  margin: 0 auto;
  padding: 28px 24px 36px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
  min-height: 100vh;
  box-sizing: border-box;
}

/* ── Front ─────────────────────────────── */

.prompt-label {
  font-size: 13px;
  letter-spacing: 0.06em;
  color: var(--text-dim);
  text-transform: uppercase;
  margin-top: 4px;
}

/* ── Unit badge ────────────────────────── */

.unit-badge {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #fff;
  padding: 3px 10px;
  border-radius: 20px;
  opacity: 0.9;
}

/* ── Sentence (hero on back) ───────────── */

.sentence-block {
  width: 100%;
}

.sentence {
  font-family: 'Noto Sans JP', sans-serif;
  font-size: 26px;
  font-weight: 600;
  line-height: 1.55;
  color: #fff;
  padding: 14px 18px;
  background: var(--surface);
  border-radius: var(--radius);
  border-left: 4px solid var(--accent);
  margin-bottom: 6px;
}

.sentence-replay {
  margin-top: 2px;
  margin-bottom: 0;
}

/* ── Vocabulary word section ───────────── */

.word-section {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.headword-block {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}

.headword {
  font-family: 'Noto Sans JP', sans-serif;
  font-size: 38px;
  font-weight: 700;
  line-height: 1.1;
  color: #fff;
}

.verb-pattern {
  font-size: 14px;
  color: var(--text-dim);
  font-style: italic;
}

.reading {
  font-family: 'Noto Sans JP', sans-serif;
  font-size: 18px;
  color: var(--accent);
  letter-spacing: 0.05em;
}

.audio-row {
  margin: 2px 0;
}

.replay-button svg { fill: var(--accent); }
.replay-button { opacity: 0.85; }
.replay-button:hover { opacity: 1; }

/* ── Meanings ──────────────────────────── */

.meanings {
  display: flex;
  flex-direction: column;
  gap: 4px;
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

/* ── Divider ───────────────────────────── */

hr.divider {
  border: none;
  border-top: 1px solid var(--divider);
  width: 100%;
  margin: 2px 0;
}

/* ── Explanation ───────────────────────── */

.explanation {
  font-family: 'Noto Sans JP', 'Inter', sans-serif;
  font-size: 14px;
  line-height: 1.75;
  color: #b8c4e0;
  padding: 10px 14px;
  background: var(--surface);
  border-radius: var(--radius);
  border-left: 3px solid var(--accent2);
  width: 100%;
  box-sizing: border-box;
}

.explanation strong { color: #fff; font-weight: 600; }
.explanation em { font-style: italic; color: #a0aac4; }

.explanation ul {
  margin: 0.3em 0;
  padding-left: 1.2em;
}

.explanation li {
  margin-top: 0.25em;
  line-height: 1.65;
}

.explanation hr {
  border: none;
  border-top: 1px solid var(--divider);
  margin: 0.5em 0;
}

.explanation .jlpt-tag {
  display: inline-block;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--text-dim);
  background: var(--surface2);
  border-radius: 3px;
  padding: 0 4px;
  margin-left: 2px;
}

/* ── More examples ─────────────────────── */

.more-examples {
  width: 100%;
}

.more-label {
  font-size: 11px;
  color: var(--text-dim);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 4px;
}

.examples-list {
  font-family: 'Noto Sans JP', sans-serif;
  font-size: 14px;
  line-height: 1.8;
  color: #9aa0be;
  padding-left: 12px;
  border-left: 2px solid var(--divider);
}

.examples-list p {
  margin: 0 0 3px 0;
}

/* ── Index tag ─────────────────────────── */

.index-tag {
  font-size: 11px;
  color: var(--text-dim);
  margin-top: auto;
  padding-top: 16px;
  align-self: flex-end;
}
"""


def build_deck(db: list[dict], clips_root: Path):
    model = genanki.Model(
        MODEL_ID,
        "N2 Vocabulary — Listening",
        fields=[
            {"name": "Index"},
            {"name": "UnitLabel"},
            {"name": "UnitColor"},
            {"name": "Headword"},
            {"name": "Reading"},
            {"name": "VerbPattern"},
            {"name": "MeaningEN"},
            {"name": "MeaningZH"},
            {"name": "WordAudio"},
            {"name": "Sentence"},
            {"name": "SentenceAudio"},
            {"name": "MoreExamples"},
            {"name": "Explanation"},
        ],
        templates=[{"name": "Listening Card", "qfmt": FRONT_TMPL, "afmt": BACK_TMPL}],
        css=CSS,
    )

    deck   = genanki.Deck(DECK_ID, "N2Words::Listening")
    media:  list[str]  = []
    media_set: set[str] = set()

    def t(v) -> str:
        return html_mod.escape(str(v or ""))

    def add_audio(clip_rel: str | None) -> str:
        if not clip_rel:
            return ""
        p = Path(clip_rel)
        if not p.is_absolute():
            p = ROOT / clip_rel.replace("/", "\\")
        if not p.exists():
            return ""
        key = p.name
        if key not in media_set:
            media_set.add(key)
            media.append(str(p))
        return f"[sound:{key}]"

    for e in db:
        idx      = e["index"]
        unit_num = e["unit"]["number"]
        unit_hdr = e["unit"].get("header", f"Unit {unit_num:02d}")
        parts    = unit_hdr.split()
        unit_label = " ".join(parts[:1] + parts[2:]) if len(parts) >= 3 else unit_hdr
        unit_color = UNIT_COLORS.get(unit_num, "#666")

        word_audio = add_audio(e.get("word_clip"))
        sent_audio = add_audio(e.get("sentence_clip"))

        examples = e.get("examples") or []
        more_html = "".join(f"<p>{html_mod.escape(ex)}</p>" for ex in examples)

        # explanation: convert markdown to HTML for Anki display
        raw_exp = e.get("explanation") or ""
        explanation = explanation_to_html(raw_exp)

        note = genanki.Note(
            model=model,
            fields=[
                str(idx),
                unit_label,
                unit_color,
                t(e.get("headword_text")),
                t(e.get("reading")),
                t(e.get("verb_pattern")),
                t(e.get("meaning_en")),
                t(e.get("meaning_zh")),
                word_audio,
                t(e.get("sentence")),
                sent_audio,
                more_html,
                explanation,
            ],
            guid=genanki.guid_for(f"n2listening_{idx}"),
            tags=[f"unit{unit_num:02d}", "N2", "listening"],
        )
        deck.add_note(note)

    return deck, media


def clip_exists(clip_rel: str | None) -> bool:
    if not clip_rel:
        return False
    p = Path(clip_rel)
    if not p.is_absolute():
        p = ROOT / clip_rel.replace("/", "\\")
    return p.exists()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db",  default="vocabulary.json")
    ap.add_argument("--out", default="output/N2Words_listening.apkg")
    ap.add_argument("--clips", default="clips")
    args = ap.parse_args()

    db_path    = ROOT / args.db
    clips_root = ROOT / args.clips

    if not db_path.exists():
        print(f"ERROR: {db_path} not found. Run make_clean_db.py first.")
        return

    db = json.loads(db_path.read_text(encoding="utf-8"))
    db.sort(key=lambda e: e["index"])

    print(f"Building listening deck for {len(db)} entries…")
    deck, media = build_deck(db, clips_root)

    pkg = genanki.Package(deck)
    pkg.media_files = media

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    pkg.write_to_file(str(out))

    explained = sum(1 for e in db if e.get("explanation"))
    no_audio  = sum(1 for e in db if not clip_exists(e.get("sentence_clip")))
    print(f"Written: {out}  ({out.stat().st_size // 1024 // 1024} MB)")
    print(f"  Notes      : {len(db)}")
    print(f"  Media      : {len(media)} files")
    print(f"  Explained  : {explained}/{len(db)}")
    print(f"  No sent audio: {no_audio}")


if __name__ == "__main__":
    main()
