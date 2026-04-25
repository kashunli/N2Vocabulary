"""Kana-based text comparison utilities.

All similarity scoring in this pipeline is done on kana-only projections rather
than raw surface text. The reason: Whisper very commonly transcribes the correct
reading but wrong kanji — e.g. it hears こうりゅう and writes 交流 when the entry
is 交竜, or writes hiragana when the entry uses kanji. Comparing kana-only
projections sidesteps the kanji/kana representation choice entirely and lets
similarity scoring reflect what was actually heard rather than how it was written.
"""
from __future__ import annotations

import difflib


def to_kana(text: str) -> str:
    """Strip everything except hiragana/katakana (U+3040–U+30FF)."""
    if not text:
        return ""
    return "".join(c for c in text if "\u3040" <= c <= "\u30ff")


def kana_similarity(a: str, b: str) -> float:
    """Return SequenceMatcher ratio on the kana-only projections of a and b."""
    ka, kb = to_kana(a), to_kana(b)
    if not ka or not kb:
        return 0.0
    return difflib.SequenceMatcher(None, ka, kb).ratio()
