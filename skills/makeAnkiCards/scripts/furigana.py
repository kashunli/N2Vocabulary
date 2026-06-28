"""Reusable Japanese furigana utilities — split words into kanji/kana segments.

Provides a segment-list model for representing how a reading maps onto a word's
surface form.  Downstream code can render the segments into HTML ruby, plain-text
parenthetical notation, or any custom format.

Examples
--------
>>> split_word("通す", "とおす")
[KanjiSegment(kanji='通', reading='とお'), KanaSegment(text='す')]

>>> split_word("勉強", "べんきょう")
[KanjiSegment(kanji='勉強', reading='べんきょう')]

>>> split_word("今日", "きょう")
[KanjiSegment(kanji='今日', reading='きょう')]

>>> to_parenthetical("通す", "とおす")
'通(とお)す'

>>> to_ruby_html("通す", "とおす")
'<ruby><rb>通</rb><rt>とお</rt></ruby>す'
"""

from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass
from typing import Union

# --- character classification ------------------------------------------------

_KANJI_RE = re.compile(r"[一-龯々〆ヵヶ]")


def _is_kanji(ch: str) -> bool:
    """Return True if *ch* is a CJK kanji character."""
    return bool(_KANJI_RE.search(ch))


def katakana_to_hiragana(text: str) -> str:
    """Convert katakana to hiragana via codepoint shift.

    Handles the standard katakana block U+30A1–U+30F6 → hiragana U+3041–U+3096.
    Characters outside that range pass through unchanged.
    """
    out: list[str] = []
    for ch in text:
        code = ord(ch)
        if 0x30A1 <= code <= 0x30F6:
            out.append(chr(code - 0x60))
        else:
            out.append(ch)
    return "".join(out)


# --- segment model -----------------------------------------------------------

@dataclass(frozen=True)
class KanjiSegment:
    """A kanji run with its reading (hiragana)."""

    kanji: str
    reading: str


@dataclass(frozen=True)
class KanaSegment:
    """Plain kana (okurigana, particles, …) — no reading needed."""

    text: str


Segment = Union[KanjiSegment, KanaSegment]


# --- core splitting logic ----------------------------------------------------

def split_word(surface: str, reading: str) -> list[Segment]:
    """Decompose a Japanese word into an ordered list of :class:`Segment`.

    The function splits off a *leading kanji run* from any trailing okurigana,
    then strips the corresponding okurigana suffix from *reading* so the
    kanji-only reading is isolated.

    Parameters
    ----------
    surface:
        The word as it appears in text (e.g. ``"通す"``).
    reading:
        Its hiragana reading (e.g. ``"とおす"``).  Must already be in hiragana;
        use :func:`katakana_to_hiragana` first if the source is UniDic katakana.

    Returns
    -------
    list[Segment]
        An ordered list of :class:`KanjiSegment` and :class:`KanaSegment`.

    Notes
    -----
    * Compound kanji (e.g. ``勉強`` → ``べんきょう``) stay as a single
      ``KanjiSegment`` because we cannot reliably split the reading between the
      individual kanji without a character-level reading dictionary.
    * Jukujikun (e.g. ``今日`` → ``きょう``) are also single segments.
    * When the kanji is not at the token start (rare), the entire surface is
      returned as a single ``KanjiSegment`` with the full reading as a fallback.
    """
    if not surface:
        return []

    if not _KANJI_RE.search(surface):
        return [KanaSegment(text=surface)]

    if not reading:
        return [KanjiSegment(kanji=surface, reading="")]

    # Find the leading kanji run.
    kanji_end = 0
    for ch in surface:
        if _is_kanji(ch):
            kanji_end += 1
        else:
            break

    kanji_part = surface[:kanji_end]
    okurigana = surface[kanji_end:]

    if not kanji_part:
        # Edge case: kanji is not at the token start.  Fall back to treating
        # the whole surface as a single KanjiSegment with the full reading.
        return [KanjiSegment(kanji=surface, reading=reading)]

    # Strip the okurigana suffix from the reading to get the kanji-only reading.
    if okurigana and reading.endswith(okurigana):
        kanji_reading = reading[: -len(okurigana)]
    else:
        # Either no okurigana, or the reading doesn't match (irregular).
        # Use the full reading for the kanji portion.
        kanji_reading = reading

    segments: list[Segment] = []
    if kanji_reading:
        segments.append(KanjiSegment(kanji=kanji_part, reading=kanji_reading))
    else:
        segments.append(KanjiSegment(kanji=kanji_part, reading=kanji_part))

    if okurigana:
        segments.append(KanaSegment(text=okurigana))

    return segments


# --- renderers ---------------------------------------------------------------

def segments_to_ruby_html(segments: list[Segment]) -> str:
    """Render *segments* as HTML with ``<ruby>`` tags for kanji.

    Kana segments are HTML-escaped and appended as plain text.
    """
    parts: list[str] = []
    for seg in segments:
        if isinstance(seg, KanjiSegment):
            parts.append(
                "<ruby>"
                f"<rb>{_html.escape(seg.kanji)}</rb>"
                f"<rt>{_html.escape(seg.reading)}</rt>"
                "</ruby>"
            )
        else:
            parts.append(_html.escape(seg.text))
    return "".join(parts)


def segments_to_parenthetical(segments: list[Segment]) -> str:
    """Render *segments* as plain text with readings in parentheses.

    Example: ``通(とお)す``, ``勉強(べんきょう)``.
    """
    parts: list[str] = []
    for seg in segments:
        if isinstance(seg, KanjiSegment):
            parts.append(f"{seg.kanji}({seg.reading})")
        else:
            parts.append(seg.text)
    return "".join(parts)


# --- convenience wrappers ----------------------------------------------------

def to_ruby_html(surface: str, reading: str) -> str:
    """Shortcut: split *surface*/*reading* and render as HTML ruby."""
    return segments_to_ruby_html(split_word(surface, reading))


def to_parenthetical(surface: str, reading: str) -> str:
    """Shortcut: split *surface*/*reading* and render as parenthetical text."""
    return segments_to_parenthetical(split_word(surface, reading))
