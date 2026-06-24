#!/usr/bin/env python3
r"""Generate N2Words.apkg - Anki deck for all N2 vocabulary entries.

Usage from D:\n2Prepare\N2Vocabulary:
    python -u skills/makeAnkiCards/scripts/make_anki.py [--out output\N2Words.apkg]

Reads the current project-level SQLite database and packages clips from clips/.
Stable deck/model/note IDs are preserved so Anki can update existing notes.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import html as html_mod

import genanki

SKILL_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from db.connect import load_entries
from anki_render import render_japanese_sentence_html

# ── Markdown → HTML for sentence explanations ────────────────────────────────

_MD_BOLD = re.compile(r'\*\*(.+?)\*\*')
_MD_ITALIC = re.compile(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)')
_MD_JLPT_TAG = re.compile(r'\[(JLPT\s*N\d+)\]')


def _md_inline(text: str) -> str:
    """Convert the small markdown subset used by generated explanations."""
    text = _MD_BOLD.sub(r'<strong>\1</strong>', text)
    text = _MD_ITALIC.sub(r'<em>\1</em>', text)
    text = _MD_JLPT_TAG.sub(r'<span class="jlpt-tag">\1</span>', text)
    return text


def explanation_to_html(text: str) -> str:
    """Render markdown explanation text into safe HTML for Anki fields."""
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
                    parts.append(_md_inline(html_mod.escape(line)))

        rendered_sections.append("\n".join(parts))

    return "\n".join(rendered_sections)

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
    {{#SentenceTranslationEN}}<div class="sentence-translation">{{SentenceTranslationEN}}</div>{{/SentenceTranslationEN}}
  </div>

  {{#MoreExample1}}
  <div class="more-examples">
    <div class="examples-label">More examples</div>
    <div class="examples-list">
      {{#MoreExample1}}<div class="example-item">{{MoreExample1}}</div>{{/MoreExample1}}
      {{#MoreExample2}}<div class="example-item">{{MoreExample2}}</div>{{/MoreExample2}}
      {{#MoreExample3}}<div class="example-item">{{MoreExample3}}</div>{{/MoreExample3}}
      {{#MoreExample4}}<div class="example-item">{{MoreExample4}}</div>{{/MoreExample4}}
      {{#MoreExample5}}<div class="example-item">{{MoreExample5}}</div>{{/MoreExample5}}
    </div>
  </div>
  {{/MoreExample1}}

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

.sentence ruby,
.example-jp ruby {
  ruby-position: over;
  ruby-align: center;
}

.sentence rt,
.example-jp rt {
  color: var(--accent);
  font-size: 0.58em;
  font-weight: 500;
  line-height: 1;
}

.sentence-translation {
  font-size: 14px;
  line-height: 1.5;
  color: #aeb8d6;
  padding: 0 14px 4px;
}

/* More examples */
.more-examples {
  width: 100%;
  margin-top: 4px;
}

.examples-label {
  font-size: 11px;
  color: var(--text-dim);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 4px;
}

.examples-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  font-size: 14px;
  line-height: 1.65;
  color: #b0b8d0;
  padding: 6px 12px;
  border-left: 2px solid var(--divider);
}

.example-item {
  min-width: 0;
}

.example-jp {
  font-family: 'Noto Sans JP', sans-serif;
  color: #d8def4;
}

.example-en {
  color: #9ca8c8;
  margin-top: 2px;
}

.example-zh {
  color: #9ca8c8;
  margin-top: 2px;
}

.example-explanation {
  color: #b8c4e0;
  margin-top: 6px;
  padding: 8px 10px;
  background: var(--surface);
  border-radius: 8px;
  border-left: 2px solid var(--accent);
}

.example-explanation strong { color: #fff; font-weight: 600; }
.example-explanation em { font-style: italic; color: #a0aac4; }

.example-explanation ul {
  margin: 0.3em 0;
  padding-left: 1.2em;
}

.example-explanation li {
  margin-top: 0.25em;
  line-height: 1.65;
}

.example-explanation .jlpt-tag {
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
        p = PROJECT_ROOT / p
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
            {"name": "SentenceTranslationEN"},
            {"name": "SentenceAudio"},
            {"name": "MoreExamples"},
            {"name": "MoreExample1"},
            {"name": "MoreExample2"},
            {"name": "MoreExample3"},
            {"name": "MoreExample4"},
            {"name": "MoreExample5"},
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
        unit_label = unit_hdr
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

        example_items = e.get("example_items") or []
        examples_all = e.get("examples_all") or e.get("examples") or []
        sentence     = e.get("sentence") or e.get("sentence_text") or (examples_all[0] if examples_all else "")
        sentence_translation_en = e.get("sentence_translation_en") or ""

        # Anki templates cannot iterate over database rows. Pre-render the
        # extra examples into one HTML field and cap the total visible sentence
        # items at five: one main sentence plus four additional examples.
        extra_items = [x for x in example_items if x.get("position") != 0 and x.get("text")]
        if not extra_items:
            extra_items = [
                {"position": i + 1, "text": text, "translation_en": ""}
                for i, text in enumerate(examples_all)
                if text
            ]
        def render_more_example(item: dict) -> str:
            jp = render_japanese_sentence_html(item.get("text") or "")
            en = html_mod.escape(str(item.get("translation_en") or ""))
            zh = html_mod.escape(str(item.get("translation_zh") or ""))
            exp = explanation_to_html(str(item.get("explanation") or ""))
            en_html = f'<div class="example-en">{en}</div>' if en else ""
            zh_html = f'<div class="example-zh">{zh}</div>' if zh else ""
            exp_html = f'<div class="example-explanation">{exp}</div>' if exp else ""
            return f'<div class="example-jp">{jp}</div>{en_html}{zh_html}{exp_html}'

        # Keep each extra example in its own Anki field/column. The template
        # renders these in source order and intentionally omits item 6+.
        more_example_fields = [render_more_example(item) for item in extra_items[:5]]
        more_example_fields.extend([""] * (5 - len(more_example_fields)))

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
                render_japanese_sentence_html(sentence),
                t(sentence_translation_en),
                sent_audio,
                "",
                *more_example_fields,
            ],
            guid=genanki.guid_for(f"n2vocab_{idx}"),
            tags=[f"unit{unit_num:02d}", f"N2"],
        )
        notes.append(note)

    return notes, media, model


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate N2Words.apkg")
    ap.add_argument("--out", default="output/N2Words.apkg")
    ap.add_argument("--db", default="output/n2vocab.sqlite")
    ap.add_argument("--clips", default="clips")
    ap.add_argument("--book", default="N2")
    args = ap.parse_args()

    clips_root = Path(args.clips)
    if not clips_root.is_absolute():
        clips_root = PROJECT_ROOT / clips_root
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path

    data = load_entries(book_code=args.book, db_path=db_path)
    data.sort(key=lambda e: e["index"])

    print(f"Building notes for {len(data)} entries…")
    notes, media, model = build_notes(data, clips_root)

    deck = genanki.Deck(DECK_ID, "耳から覚える::N2Words")
    for note in notes:
        deck.add_note(note)

    package = genanki.Package(deck)
    package.media_files = [str(p) for p in media]

    out = Path(args.out)
    if not out.is_absolute():
        out = PROJECT_ROOT / out
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
