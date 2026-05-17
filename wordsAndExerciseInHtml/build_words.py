#!/usr/bin/env python3
"""
build_words.py — Rebuild static HTML vocabulary pages for the N2 book.

Reads:  ../output/n2vocab.sqlite    (project root)
Audio:  ../clips/unitXX/wordN.mp3   (project root clips/)
Writes: wordsAndExerciseInHtml/
          index.html
          words/
            index.html
            by_unit/
              unit_01.html … unit_13.html

Run from project root:
    python wordsAndExerciseInHtml/build_words.py
Or from this directory:
    python build_words.py
"""

import html
import re
import sys
from collections import OrderedDict, defaultdict
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
OUT_ROOT = SCRIPT_DIR  # wordsAndExerciseInHtml/

# Read entries from SQLite. The old vocabulary.json source has been retired.
sys.path.insert(0, str(PROJECT_ROOT))
from db import DB_PATH, load_entries  # noqa: E402

# ── CSS ────────────────────────────────────────────────────────────────────────

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
    .example-translation {
      color: var(--muted);
      font-size: 0.92rem;
      line-height: 1.45;
    }
    .example-translation .en { color: var(--ink); font-weight: 500; }
    .example-translation .zh { color: var(--muted); }
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
    .entry-audio { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
    .audio-label {
      font-size: 0.75rem; font-weight: 700; letter-spacing: 0.06em;
      color: var(--muted); text-transform: uppercase;
    }
    audio { height: 28px; vertical-align: middle; }
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


# ── HTML shell ─────────────────────────────────────────────────────────────────


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
    k = html.escape(kanji)
    r = html.escape(reading)
    if kanji == reading:
        return k
    return f"<ruby><rb>{k}</rb><rt>{r}</rt></ruby>"


_MD_BOLD = re.compile(r"\*\*(.+?)\*\*")
_MD_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_MD_JLPT_TAG = re.compile(r"\[(JLPT\s*N\d+)\]")


def _md_inline(text: str) -> str:
    text = _MD_BOLD.sub(r"<strong>\1</strong>", text)
    text = _MD_ITALIC.sub(r"<em>\1</em>", text)
    text = _MD_JLPT_TAG.sub(r'<span class="jlpt-tag">\1</span>', text)
    return text


def explanation_html(text: str) -> str:
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
                        items.append(("<p>", list(current)))
                        current = []
                    in_list = True
                current.append(stripped[2:])
            else:
                if in_list:
                    items.append(("<ul>", list(current)))
                    current = []
                    in_list = False
                current.append(line)

        if in_list:
            items.append(("<ul>", list(current)))
        elif current:
            items.append(("<p>", list(current)))

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
                        parts.append(f'<span class="explanation-nuance">{rendered}</span>')
                    else:
                        parts.append(rendered)

        rendered_sections.append("\n".join(parts))

    return "<hr>".join(rendered_sections)


def clip_rel_path(clip_path: str) -> str:
    """
    Convert a project-root clip path from SQLite to a URL relative to
    wordsAndExerciseInHtml/words/by_unit/.

    Historical rows may store: output\\clips\\unit01\\word1.mp3
    Actual files live at:    <project_root>/clips/unit01/word1.mp3
    Relative from by_unit/:  ../../../clips/unit01/word1.mp3
    """
    p = clip_path.replace("\\", "/")
    # Strip leading "output/" if present — clips now live at project root
    p = re.sub(r"^output/", "", p)
    # p is now: clips/unit01/word1.mp3
    return "../../../" + p


# ── Entry HTML ─────────────────────────────────────────────────────────────────


def render_entry(e: dict) -> str:
    idx = e["index"]
    kanji = e.get("headword_text") or e.get("kanji", "")
    reading = e.get("reading", "")
    meaning_en = e.get("meaning_en", "")
    meaning_zh = e.get("meaning_zh", "")
    sentence = e.get("sentence", "")
    sentence_translation_en = e.get("sentence_translation_en", "")
    sentence_translation_zh = e.get("sentence_translation_zh", "")
    examples = e.get("examples") or []
    example_items = e.get("example_items") or []
    explanation = e.get("explanation", "")
    word_clip = e.get("word_clip")
    sentence_clip = e.get("sentence_clip")

    parts = [f'<article class="entry" id="w{idx}">']

    parts.append('  <div class="entry-top">')
    parts.append('    <div class="entry-main">')
    parts.append(f'      <div class="entry-id">{idx:03d}</div>')
    parts.append(f'      <h3 class="entry-kanji">{headword_html(kanji, reading)}</h3>')
    parts.append("    </div>")
    parts.append('    <div class="entry-glosses">')
    if meaning_en:
        parts.append(f'      <div class="meaning meaning-en">{html.escape(meaning_en)}</div>')
    if meaning_zh:
        parts.append(f'      <div class="meaning meaning-zh">{html.escape(meaning_zh)}</div>')
    parts.append("    </div>")
    parts.append("  </div>")

    if example_items:
        all_examples = example_items
    else:
        all_examples = []
        if sentence:
            all_examples.append({
                "text": sentence,
                "translation_en": sentence_translation_en,
                "translation_zh": sentence_translation_zh,
            })
        all_examples.extend({"text": text} for text in examples)

    all_sentences = [item for item in all_examples if item.get("text")]
    if all_sentences:
        parts.append('  <section class="entry-block entry-examples">')
        parts.append('    <ul class="example-list">')
        for item in all_sentences:
            s = html.escape(item.get("text") or "")
            tr_en = item.get("translation_en") or ""
            tr_zh = item.get("translation_zh") or ""
            tr_parts = []
            if tr_en:
                tr_parts.append(f'<span class="en">{html.escape(tr_en)}</span>')
            if tr_zh:
                tr_parts.append(f'<span class="zh">{html.escape(tr_zh)}</span>')
            tr_html = (
                '<span class="example-translation">'
                + " / ".join(tr_parts)
                + "</span>"
                if tr_parts else ""
            )
            parts.append(
                '      <li class="example-line no-marker">'
                '<span class="example-body">'
                f'<span class="example-text">{s}</span>'
                f"{tr_html}"
                "</span></li>"
            )
        parts.append("    </ul>")
        parts.append("  </section>")

    if explanation:
        exp_html = explanation_html(explanation)
        parts.append('  <section class="entry-block entry-explanation">')
        parts.append(f'    <div class="explanation">{exp_html}</div>')
        parts.append("  </section>")

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
    chapter = '    <section class="chapter">\n' + "\n".join(entry_parts) + "\n    </section>"
    body = f'  <main class="sheet">\n{hero}\n{chapter}\n  </main>'
    return html_page(f"Unit {num_str} {unit_title} — N2 語彙", body)


# ── Words index ────────────────────────────────────────────────────────────────


def render_words_index(unit_info: list) -> str:
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
        '        <span class="meta-pill">·</span>\n'
        '        <a class="meta-pill" href="cards/index.html" style="color: var(--ink); text-decoration: underline;">'
        'Card view (with known / flagged marks) →</a>\n'
        "      </div>\n"
        "    </section>"
    )
    body = (
        f'  <main class="sheet">\n{hero}\n'
        f'    <section class="chapter">\n      {grid}\n    </section>\n  </main>'
    )
    return html_page("N2 語彙 — All Units", body)


# ── Landing page ───────────────────────────────────────────────────────────────


def render_landing(total: int, num_units: int) -> str:
    hero = (
        '    <section class="hero">\n'
        '      <div class="eyebrow">Study Materials</div>\n'
        "      <h1>N2 語彙トレーニング</h1>\n"
        '      <div class="hero-meta">\n'
        f'        <span class="meta-pill">{total:,} entries · {num_units} units</span>\n'
        "      </div>\n"
        "    </section>"
    )
    nav = (
        "    <nav>\n"
        '      <div class="nav-grid">\n'
        '        <a class="nav-card" href="words/index.html">\n'
        '          <span class="nav-card-title">Words</span>\n'
        '          <span class="nav-card-desc">Browse all vocabulary entries by unit, '
        "with readings, example sentences, grammar explanations, and audio.</span>\n"
        "        </a>\n"
        '        <a class="nav-card" href="exercises/index.html">\n'
        '          <span class="nav-card-title">Exercises</span>\n'
        '          <span class="nav-card-desc">Practice with unit exercises and summary tests '
        "with answer keys.</span>\n"
        "        </a>\n"
        "      </div>\n"
        "    </nav>"
    )
    body = f'  <main class="sheet">\n{hero}\n{nav}\n  </main>'
    return html_page("N2 語彙トレーニング", body, LANDING_EXTRA_CSS)


# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    if not DB_PATH.exists():
        print(
            f"ERROR: {DB_PATH} not found. Run `python db/import_vocabulary.py` first.",
            file=sys.stderr,
        )
        sys.exit(1)

    data = load_entries(book_code="N2")

    by_unit: dict[int, list] = defaultdict(list)
    for e in data:
        by_unit[e["unit"]["number"]].append(e)

    unit_meta: OrderedDict[int, tuple] = OrderedDict()
    for unit_num in sorted(by_unit):
        entries = by_unit[unit_num]
        first_header = entries[0]["unit"]["header"]
        short_title = re.sub(r"^Unit\s+\d+\s+", "", first_header).strip()
        short_title = re.sub(r"\s*&\s*Column.*$", "", short_title).strip()
        unit_meta[unit_num] = (short_title, len(entries))

    words_dir = OUT_ROOT / "words"
    by_unit_dir = words_dir / "by_unit"
    by_unit_dir.mkdir(parents=True, exist_ok=True)

    total = len(data)
    num_units = len(unit_meta)

    landing_path = OUT_ROOT / "index.html"
    landing_path.write_text(render_landing(total, num_units), encoding="utf-8")
    print(f"  wrote {landing_path}")

    unit_info = [(num, title, count) for num, (title, count) in unit_meta.items()]
    words_index_path = words_dir / "index.html"
    words_index_path.write_text(render_words_index(unit_info), encoding="utf-8")
    print(f"  wrote {words_index_path}")

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
