"""HTML render helpers shared by the Anki deck builders."""
from __future__ import annotations

import html
import re

_KANJI_RE = re.compile(r"[一-龯々〆ヵヶ]")

try:
    import unidic_lite
    from fugashi import Tagger

    _TAGGER = Tagger(f'-d "{unidic_lite.DICDIR}"')
except Exception:
    _TAGGER = None


def _katakana_to_hiragana(text: str) -> str:
    """Convert katakana readings from UniDic into hiragana for furigana."""
    out = []
    for ch in text:
        code = ord(ch)
        if 0x30A1 <= code <= 0x30F6:
            out.append(chr(code - 0x60))
        else:
            out.append(ch)
    return "".join(out)


def render_japanese_sentence_html(text: str) -> str:
    """Return escaped sentence HTML with kanji tokens annotated as ruby.

    The source sentences are plain text from SQLite. We only add furigana to
    tokens that visibly contain kanji, leaving kana particles and punctuation
    unwrapped so the rendered sentence stays readable.
    """
    raw = str(text or "")
    if not raw:
        return ""
    if _TAGGER is None:
        return html.escape(raw)

    parts = []
    for token in _TAGGER(raw):
        surface = token.surface
        if not _KANJI_RE.search(surface):
            parts.append(html.escape(surface))
            continue

        reading = getattr(token.feature, "kana", "") or getattr(token.feature, "pron", "")
        reading = _katakana_to_hiragana(reading)
        if not reading:
            parts.append(html.escape(surface))
            continue

        parts.append(
            "<ruby>"
            f"<rb>{html.escape(surface)}</rb>"
            f"<rt>{html.escape(reading)}</rt>"
            "</ruby>"
        )
    return "".join(parts)
