"""HTML render helpers shared by the Anki deck builders."""
from __future__ import annotations

import html
import re

from furigana import _KANJI_RE, katakana_to_hiragana, to_ruby_html

try:
    import unidic_lite
    from fugashi import Tagger

    _TAGGER = Tagger(f'-d "{unidic_lite.DICDIR}"')
except Exception:
    _TAGGER = None


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

        reading = getattr(token.feature, "kana", "") or getattr(token.feature, "pron", "") or ""
        reading = katakana_to_hiragana(reading)
        if not reading:
            parts.append(html.escape(surface))
            continue

        parts.append(to_ruby_html(surface, reading))
    return "".join(parts)
