"""
Runtime word-page rendering for the local SQLite-backed study server.

The static builders remain the visual template source. This module gathers the
DB rows once per request, groups them by unit, and calls the existing long-page
and card-grid renderers so runtime pages keep the current design.
"""

from __future__ import annotations

import re
from collections import OrderedDict, defaultdict

import build_word_cards
import build_words


def _short_title(header: str) -> str:
    title = re.sub(r"^Unit\s+\d+\s+", "", header).strip()
    title = re.sub(r"\s*&\s*Column.*$", "", title).strip()
    return title or header


def build_context(entries: list[dict]) -> tuple[dict[int, list[dict]], list[tuple[int, str, int]]]:
    """Group DB-shaped entries into the unit metadata the templates expect."""
    by_unit: dict[int, list[dict]] = defaultdict(list)
    for entry in entries:
        by_unit[entry["unit"]["number"]].append(entry)

    unit_meta: OrderedDict[int, tuple[str, int]] = OrderedDict()
    for unit_num in sorted(by_unit):
        unit_entries = by_unit[unit_num]
        title = _short_title(unit_entries[0]["unit"]["header"])
        unit_meta[unit_num] = (title, len(unit_entries))

    unit_info = [(num, title, count) for num, (title, count) in unit_meta.items()]
    return by_unit, unit_info


def render_landing(entries: list[dict]) -> str:
    by_unit, _unit_info = build_context(entries)
    return build_words.render_landing(total=len(entries), num_units=len(by_unit))


def render_words_index(entries: list[dict]) -> str:
    _by_unit, unit_info = build_context(entries)
    return build_words.render_words_index(unit_info)


def render_long_unit(entries: list[dict], unit_num: int) -> str | None:
    by_unit, unit_info = build_context(entries)
    unit_entries = by_unit.get(unit_num)
    if not unit_entries:
        return None
    title_by_unit = {num: title for num, title, _count in unit_info}
    return build_words.render_unit_page(unit_num, title_by_unit[unit_num], unit_entries)


def render_card_index(entries: list[dict]) -> str:
    _by_unit, unit_info = build_context(entries)
    return build_word_cards.render_index(unit_info)


def render_card_unit(entries: list[dict], unit_num: int) -> str | None:
    by_unit, unit_info = build_context(entries)
    unit_entries = by_unit.get(unit_num)
    if not unit_entries:
        return None
    title_by_unit = {num: title for num, title, _count in unit_info}
    return build_word_cards.render_unit_page(unit_num, title_by_unit[unit_num], unit_entries)
