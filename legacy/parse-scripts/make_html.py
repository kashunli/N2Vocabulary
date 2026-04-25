#!/usr/bin/env python3
"""
make_html.py — Generate static HTML vocabulary pages for the N2 book.

Output layout:
  output/html/
    index.html                  ← landing page
    words/
      index.html                ← unit grid
      by_unit/
        unit_01.html … unit_13.html
"""

import html
import json
import os
import re
from collections import OrderedDict, defaultdict
from pathlib import Path

DB_PATH = Path("output/vocabulary.json")
OUT_ROOT = Path("output/html")

# ── Shared CSS (same as N3WordsDigital pattern) ────────────────────────────────

SHARED_CSS = """
    * { box-sizing: border-box; }
    ruby { ruby-position: over; ruby-align: center; }
    rt {
      font-size: 0.46em; line-height: 1;
      color: var(--muted); letter-spacing: 0.01em;
    }
    :root {
      --paper: #ffffff; --ink: #1a1a1a;
      --muted: #626262; --line: #d7d7d7; --line-strong: #a7a7a7;
    }
    body {
      margin: 0;
      font-family: "Skolar Sans PE", "Avenir Next", "Hiragino Sans", "Yu Gothic", sans-serif;
      background: var(--paper); color: var(--ink); line-height: 1.55;
    }
    .sheet { max-width: 860px; margin: 0 auto; padding: 36px 20px 60px; }
    .hero {
      padding-bottom: 14px;
      border-bottom: 2px solid var(--line-strong);
      margin-bottom: 12px;
    }
    .eyebrow {
      font-size: 0.82rem; letter-spacing: 0.08em;
      color: var(--muted); margin-bottom: 6px;
    }
    .hero h1 {
      margin: 0;
      font-family: "Iowan Old Style", "Baskerville", "Hiragino Mincho ProN", "Yu Mincho", serif;
      font-size: clamp(1.8rem, 3.3vw, 2.6rem);
      line-height: 1.15; font-weight: 600;
    }
    .hero-meta { display: flex; flex-wrap: wrap; gap: 8px 12px; margin: 10px 0 0; }
    .meta-pill { padding: 0; font-size: 0.92rem; color: var(--muted); }
    .back-link {
      display: inline-flex; align-items: center;
      margin-bottom: 14px; color: var(--muted);
      text-decoration: none; font-size: 0.92rem;
      font-weight: 600; letter-spacing: 0.01em;
    }
    .back-link:hover, .back-link:focus-visible { color: var(--ink); text-decoration: underline; }
    .entry { padding: 18px 0 20px; border-top: 1px solid var(--line); }
    .entry:first-of-type { border-top: 0; }
    .entry-top {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(220px, 290px);
      gap: 14px; align-items: start;
    }
    .entry-id {
      margin-bottom: 6px; font-size: 0.78rem; line-height: 1;
      font-weight: 600; letter-spacing: 0.05em; color: var(--muted);
    }
    .entry-kanji {
      margin: 0;
      font-family: "Iowan Old Style", "Baskerville", "Hiragino Mincho ProN", "Yu Mincho", serif;
      font-size: 1.82rem; line-height: 1.15; font-weight: 600;
    }
    .entry-type {
      margin-top: 6px; font-size: 0.96rem;
      font-weight: 600; color: var(--muted); letter-spacing: 0.01em;
    }
    .type-token { display: inline-block; margin-right: 0.18em; }
    .entry-glosses { display: grid; gap: 4px; padding-top: 3px; }
    .meaning-en { font-weight: 600; }
    .meaning-zh { color: var(--muted); font-size: 0.96rem; }
    .entry-block { margin-top: 12px; padding-left: 0; }
    .example-list { margin: 0; padding-left: 0; list-style: none; }
    .example-line {
      display: grid; grid-template-columns: 32px 1fr;
      gap: 8px; align-items: start;
    }
    .example-line.no-marker { grid-template-columns: 1fr; gap: 0; }
    .example-line + .example-line { margin-top: 6px; }
    .example-marker {
      display: inline-flex; justify-content: center;
      color: var(--ink); font-weight: 700;
    }
    .example-text { font-size: 1.03rem; }
    .example-body { display: grid; gap: 4px; }
    /* Explanation block (N2-specific) */
    .entry-explanation .explanation {
      font-size: 0.88rem;
      line-height: 1.65;
      color: var(--muted);
      background: color-mix(in srgb, var(--muted) 7%, var(--paper));
      border-radius: 6px;
      padding: 10px 14px;
    }
    .entry-explanation .explanation ul {
      margin: 0.3em 0;
      padding-left: 1.4em;
      list-style: disc;
    }
    .entry-explanation .explanation li {
      margin-top: 0.25em;
      line-height: 1.6;
    }
    .entry-explanation .explanation p {
      margin: 0.3em 0;
    }
    .entry-explanation .explanation hr {
      border: none;
      border-top: 1px solid var(--line);
      margin: 0.6em 0;
    }
    .entry-explanation .explanation .jlpt-tag {
      display: inline-block;
      font-size: 0.72rem;
      font-weight: 700;
      letter-spacing: 0.04em;
      color: var(--muted);
      background: color-mix(in srgb, var(--muted) 12%, var(--paper));
      border-radius: 3px;
      padding: 0 4px;
      margin-left: 2px;
    }
    .explanation-nuance { color: var(--ink); font-weight: 600; }
    /* Audio controls */
    .entry-audio { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
    .audio-label {
      font-size: 0.75rem; font-weight: 700; letter-spacing: 0.06em;
      color: var(--muted); text-transform: uppercase;
    }
    audio { height: 28px; vertical-align: middle; }
    /* Unit grid (for index page) */
    .unit-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 16px; padding: 24px 0;
    }
    .unit-card {
      display: flex; flex-direction: column; gap: 6px;
      padding: 16px 20px;
      border: 1px solid color-mix(in srgb, var(--muted) 25%, transparent);
      border-radius: 8px; text-decoration: none; color: inherit;
      transition: background 0.15s;
    }
    .unit-card:hover { background: color-mix(in srgb, var(--muted) 8%, transparent); }
    .unit-num {
      font-size: 0.78rem; font-weight: 700; letter-spacing: 0.08em;
      color: var(--muted); text-transform: uppercase;
    }
    .unit-title { font-size: 1rem; font-weight: 600; }
    .unit-meta { font-size: 0.76rem; color: var(--muted); }
    @media (max-width: 760px) {
      .sheet { padding: 18px 14px 36px; }
      .entry { padding: 16px 0 18px; }
      .entry-top { grid-template-columns: 1fr; }
      .entry-glosses { grid-column: auto; }
    }
"""

LANDING_EXTRA_CSS = """
    .nav-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 20px; padding: 28px 0;
    }
    .nav-card {
      display: flex; flex-direction: column; gap: 8px;
      padding: 24px 28px;
      border: 1px solid color-mix(in srgb, var(--muted) 25%, transparent);
      border-radius: 10px; text-decoration: none; color: inherit;
      transition: background 0.15s;
    }
    .nav-card:hover { background: color-mix(in srgb, var(--muted) 8%, transparent); }
    .nav-card-title {
      font-size: 1.25rem; font-weight: 700;
      font-family: "Iowan Old Style", "Baskerville", "Hiragino Mincho ProN", "Yu Mincho", serif;
    }
    .nav-card-desc { font-size: 0.9rem; color: var(--muted); }
"""


def html_page(title: str, body: str, extra_css: str = "") -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="ja" lang="ja">\n'
        "<head>\n"
        '  <meta charset="utf-8" />\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        f"  <title>{html.escape(title)}</title>\n"
        '  <style type="text/css">\n' + SHARED_CSS + extra_css + "  </style>\n"
        "</head>\n"
        "<body>\n" + body + "\n</body>\n</html>\n"
    )


# ── Helpers ────────────────────────────────────────────────────────────────────


def headword_html(kanji: str, reading: str) -> str:
    """Return headword with ruby furigana, or plain kana if kanji == reading."""
    k = html.escape(kanji)
    r = html.escape(reading)
    if kanji == reading:
        return k
    return f"<ruby><rb>{k}</rb><rt>{r}</rt></ruby>"


# ── Markdown → HTML for explanations ──────────────────────────────────────────

_MD_BOLD = re.compile(r"\*\*(.+?)\*\*")
_MD_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_MD_JLPT_TAG = re.compile(r"\[(JLPT\s*N\d+)\]")


def _md_inline(text: str) -> str:
    """Convert inline markdown: **bold**, *italic*, [JLPT N2]."""
    text = _MD_BOLD.sub(r"<strong>\1</strong>", text)
    text = _MD_ITALIC.sub(r"<em>\1</em>", text)
    text = _MD_JLPT_TAG.sub(r'<span class="jlpt-tag">\1</span>', text)
    return text


def explanation_html(text: str) -> str:
    """Render explanation text with markdown support.

    Handles:
    - **bold** → <strong>
    - *italic* → <em>
    - --- on its own line → <hr>
    - Lines starting with '- ' → <li>
    - [JLPT N2] → styled tag
    - 👉 lines → .explanation-nuance (legacy support)
    """
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
                    # Flush current non-list content
                    if current:
                        items.append(("<p>", "\n".join(current)))
                        current = []
                    in_list = True
                current.append(stripped[2:])  # strip "- "
            else:
                if in_list:
                    items.append(("<ul>", current))
                    current = []
                    in_list = False
                current.append(line)

        # Flush remaining
        if in_list:
            items.append(("<ul>", current))
        elif current:
            items.append(("<p>", current))

        # Render this section
        parts = []
        for tag, lines_group in items:
            if tag == "<ul>":
                li_items = "".join(
                    f"<li>{_md_inline(html.escape(li))}</li>" for li in lines_group
                )
                parts.append(f"<ul>{li_items}</ul>")
            elif tag == "<p>":
                for line in lines_group:
                    escaped = html.escape(line)
                    rendered = _md_inline(escaped)
                    if line.strip().startswith("👉"):
                        parts.append(
                            f'<span class="explanation-nuance">{rendered}</span>'
                        )
                    else:
                        parts.append(rendered)

        rendered_sections.append("\n".join(parts))

    return "\n".join(rendered_sections)


def clip_rel_path(clip_path: str) -> str:
    """
    Convert 'output/clips/unit01/word1.mp3' or 'output\\clips\\unit01\\word1.mp3'
    → '../../../clips/unit01/word1.mp3'
    (relative from output/html/words/by_unit/)
    """
    # Normalize Windows backslashes to forward slashes
    rel = clip_path.replace("\\", "/")
    # Strip leading 'output/'
    rel = re.sub(r"^output/", "", rel)
    return "../../../" + rel


# ── Entry HTML ─────────────────────────────────────────────────────────────────


def render_entry(e: dict) -> str:
    idx = e["index"]
    kanji = e.get("headword_text") or e.get("kanji", "")
    reading = e.get("reading", "")
    verb_pattern = e.get("verb_pattern")
    meaning_en = e.get("meaning_en", "")
    meaning_zh = e.get("meaning_zh", "")
    sentence = e.get("sentence", "")
    examples = e.get("examples") or []
    explanation = e.get("explanation", "")
    word_clip = e.get("word_clip")
    sentence_clip = e.get("sentence_clip")

    parts = ['<article class="entry">']

    # ── entry-top ──────────────────────────────────────────────────────────────
    parts.append('  <div class="entry-top">')
    parts.append('    <div class="entry-main">')
    parts.append(f'      <div class="entry-id">{idx:03d}</div>')
    parts.append(f'      <h3 class="entry-kanji">{headword_html(kanji, reading)}</h3>')
    if verb_pattern:
        vp = html.escape(verb_pattern)
        parts.append(
            f'      <div class="entry-type"><span class="type-token">{vp}</span></div>'
        )
    parts.append("    </div>")
    parts.append('    <div class="entry-glosses">')
    if meaning_en:
        parts.append(
            f'      <div class="meaning meaning-en">{html.escape(meaning_en)}</div>'
        )
    if meaning_zh:
        parts.append(
            f'      <div class="meaning meaning-zh">{html.escape(meaning_zh)}</div>'
        )
    parts.append("    </div>")
    parts.append("  </div>")

    # ── examples ───────────────────────────────────────────────────────────────
    all_sentences = ([sentence] if sentence else []) + list(examples)
    if all_sentences:
        parts.append('  <section class="entry-block entry-examples">')
        parts.append('    <ul class="example-list">')
        for sent in all_sentences:
            s = html.escape(sent)
            parts.append(
                '      <li class="example-line no-marker">'
                '<span class="example-body">'
                f'<span class="example-text">{s}</span>'
                "</span></li>"
            )
        parts.append("    </ul>")
        parts.append("  </section>")

    # ── explanation ────────────────────────────────────────────────────────────
    if explanation:
        exp_html = explanation_html(explanation)
        parts.append('  <section class="entry-block entry-explanation">')
        parts.append(f'    <div class="explanation">{exp_html}</div>')
        parts.append("  </section>")

    # ── audio ──────────────────────────────────────────────────────────────────
    if word_clip or sentence_clip:
        parts.append('  <section class="entry-block entry-audio">')
        if word_clip:
            src = clip_rel_path(word_clip)
            parts.append(
                f'    <span class="audio-label">Word</span>'
                f'<audio controls src="{html.escape(src)}" preload="none"></audio>'
            )
        if sentence_clip:
            src = clip_rel_path(sentence_clip)
            parts.append(
                f'    <span class="audio-label">Sentence</span>'
                f'<audio controls src="{html.escape(src)}" preload="none"></audio>'
            )
        parts.append("  </section>")

    parts.append("</article>")
    return "\n".join(parts)


# ── Unit page ──────────────────────────────────────────────────────────────────


def render_unit_page(unit_num: int, unit_title: str, entries: list) -> str:
    num_str = f"{unit_num:02d}"
    count = len(entries)

    hero = (
        f'    <section class="hero">\n'
        f'      <a class="back-link" href="../index.html">← Back to all units</a>\n'
        f'      <div class="eyebrow">Unit {num_str}</div>\n'
        f"      <h1>{html.escape(unit_title)}</h1>\n"
        f'      <div class="hero-meta">\n'
        f'        <span class="meta-pill">{count} words</span>\n'
        f"      </div>\n"
        f"    </section>"
    )

    entry_parts = [render_entry(e) for e in entries]
    chapter = (
        '    <section class="chapter">\n' + "\n".join(entry_parts) + "\n    </section>"
    )

    body = f'  <main class="sheet">\n{hero}\n{chapter}\n  </main>'
    return html_page(f"Unit {num_str} {unit_title} — N2 語彙", body)


# ── Words index ────────────────────────────────────────────────────────────────


def render_words_index(unit_info: list) -> str:
    """unit_info: list of (unit_num, short_title, count)"""
    total = sum(c for _, _, c in unit_info)
    cards = []
    for num, title, count in unit_info:
        num_str = f"{num:02d}"
        href = f"by_unit/unit_{num_str}.html"
        cards.append(
            f'<a class="unit-card" href="{href}">'
            f'<span class="unit-num">Unit {num_str}</span>'
            f'<span class="unit-title">{html.escape(title)}</span>'
            f'<span class="unit-meta">{count} words</span>'
            f"</a>"
        )
    grid = '<div class="unit-grid">' + "".join(cards) + "</div>"
    hero = (
        '    <section class="hero">\n'
        '      <a class="back-link" href="../index.html">← Back to study index</a>\n'
        '      <div class="eyebrow">All Units</div>\n'
        "      <h1>N2 語彙トレーニング</h1>\n"
        '      <div class="hero-meta">\n'
        f'        <span class="meta-pill">{len(unit_info)} units</span>\n'
        f'        <span class="meta-pill">{total} words total</span>\n'
        "      </div>\n"
        "    </section>"
    )
    body = f'  <main class="sheet">\n{hero}\n    <section class="chapter">\n      {grid}\n    </section>\n  </main>'
    return html_page("N2 語彙 — All Units", body)


# ── Landing page ───────────────────────────────────────────────────────────────


def render_landing() -> str:
    hero = (
        '    <section class="hero">\n'
        '      <div class="eyebrow">Study Materials</div>\n'
        "      <h1>N2 語彙トレーニング</h1>\n"
        '      <div class="hero-meta">\n'
        '        <span class="meta-pill">1,142 entries · 13 units</span>\n'
        "      </div>\n"
        "    </section>"
    )
    nav = (
        "    <nav>\n"
        '      <div class="nav-grid">\n'
        '        <a class="nav-card" href="words/index.html">\n'
        '          <span class="nav-card-title">Words</span>\n'
        '          <span class="nav-card-desc">Browse all 1,142 vocabulary entries by unit, with readings, meanings, example sentences, and grammar explanations.</span>\n'
        "        </a>\n"
        "      </div>\n"
        "    </nav>"
    )
    body = f'  <main class="sheet">\n{hero}\n{nav}\n  </main>'
    return html_page("N2 語彙トレーニング", body, LANDING_EXTRA_CSS)


# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    with open(DB_PATH, encoding="utf-8") as f:
        data = json.load(f)

    # Group entries by unit number, preserving order
    by_unit: dict[int, list] = defaultdict(list)
    for e in data:
        by_unit[e["unit"]["number"]].append(e)

    # Collect unit metadata: unit_num → (short_title, count)
    unit_meta: OrderedDict[int, tuple] = OrderedDict()
    for unit_num in sorted(by_unit):
        entries = by_unit[unit_num]
        first_header = entries[0]["unit"]["header"]
        # Extract short title: "Unit 01 名詞 A" → "名詞 A"
        short_title = re.sub(r"^Unit\s+\d+\s+", "", first_header).strip()
        # Also strip any trailing "& Column …" suffix that leaked in
        short_title = re.sub(r"\s*&\s*Column.*$", "", short_title).strip()
        unit_meta[unit_num] = (short_title, len(entries))

    # Create output dirs
    words_dir = OUT_ROOT / "words"
    by_unit_dir = words_dir / "by_unit"
    by_unit_dir.mkdir(parents=True, exist_ok=True)

    # Landing page
    landing_path = OUT_ROOT / "index.html"
    landing_path.write_text(render_landing(), encoding="utf-8")
    print(f"  wrote {landing_path}")

    # Words index
    unit_info = [(num, title, count) for num, (title, count) in unit_meta.items()]
    words_index_path = words_dir / "index.html"
    words_index_path.write_text(render_words_index(unit_info), encoding="utf-8")
    print(f"  wrote {words_index_path}")

    # Unit pages
    for unit_num, entries in sorted(by_unit.items()):
        short_title, _ = unit_meta[unit_num]
        unit_html = render_unit_page(unit_num, short_title, entries)
        out_path = by_unit_dir / f"unit_{unit_num:02d}.html"
        out_path.write_text(unit_html, encoding="utf-8")
        print(f"  wrote {out_path}  ({len(entries)} entries)")

    total_pages = 1 + 1 + len(by_unit)
    print(f"\nDone. {total_pages} HTML files written to {OUT_ROOT}/")


if __name__ == "__main__":
    main()
