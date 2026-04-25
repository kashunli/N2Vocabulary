#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
OCR_DIR = ROOT / "ocr" / "pages"
OUTPUT_DIR = ROOT / "structured"

ENTRY_START_RE = re.compile(r"^(?:#+\s*)?(\d{1,4})\s+(.+)$")
QUESTION_RE = re.compile(r"^(\d+)[\.\)]\s*(.+)$")
ROMAN_SECTION_RE = re.compile(r"^(?:#+\s*)?([IVXⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+)\s+(.+)$")
SUBSECTION_RE = re.compile(r"^(?:#+\s*)?([A-Z])\s*$")
IMAGE_RE = re.compile(r"!\[(.*?)\]\((.*?)\)")
PAGE_DIR_RE = re.compile(r"page-(\d+)$")
SECTION_CODE_RE = re.compile(r"^(?:#+\s*)?(\d+-\d+)$")
RELATION_LABEL_RE = re.compile(r"(?:(?<=^)|(?<=[\s　]))(連|合|対|類|関|慣|問|答|間|会|意|目|台|■|☐|☑|※|注)(?=[\s　])")
LATIN_GLOSS_RE = re.compile(
    r"^(?P<surface>.+?)\s+(?P<gloss>(?:\([A-Za-z0-9 ;,\-']+\)\s*)?[A-Za-z][A-Za-z0-9 ;,\-\(\)'.]+)$"
)
TRANSLATION_ONLY_RE = re.compile(r"^[^／/]+(?:\s*[／/]\s*[^／/]+){1,3}$")

RELATION_LABEL_MAP = {
    "連": "collocation",
    "合": "compound",
    "対": "antonym",
    "類": "synonym",
    "関": "related",
    "慣": "set_phrase",
    "問": "prompt",
    "答": "answer",
}


@dataclass
class PageSource:
    page_number: int
    markdown_path: Path


@dataclass
class ParseConfig:
    source_dir: Path = OCR_DIR
    output_dir: Path = OUTPUT_DIR
    page_numbers: set[int] | None = None
    clean_output: bool = False
    print_stats: bool = False


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert OCR markdown under ocr/pages/page-*/markdown.md into "
            "page-level JSON files in structured/."
        )
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=OCR_DIR,
        help="Directory containing page-* OCR folders. Default: %(default)s",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory that will receive page_###.json output. Default: %(default)s",
    )
    parser.add_argument(
        "--page",
        dest="pages",
        type=int,
        action="append",
        help="Parse only the given page number. Repeat to target multiple pages.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete existing page_*.json files from the output directory before writing new ones.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print a summary of generated page types after parsing completes.",
    )
    return parser


def parse_args() -> ParseConfig:
    args = build_argument_parser().parse_args()
    return ParseConfig(
        source_dir=args.source_dir.resolve(),
        output_dir=args.output_dir.resolve(),
        page_numbers=set(args.pages) if args.pages else None,
        clean_output=args.clean,
        print_stats=args.stats,
    )


def main() -> None:
    config = parse_args()
    parse_book(config)


def parse_book(config: ParseConfig) -> list[dict]:
    config.output_dir.mkdir(exist_ok=True)
    if config.clean_output:
        for path in sorted(config.output_dir.glob("page_*.json")):
            path.unlink()

    results: list[dict] = []
    for page in iter_pages(config.source_dir, config.page_numbers):
        out_path = config.output_dir / f"page_{page.page_number:03}.json"
        structured = parse_page(page, config.source_dir)
        out_path.write_text(
            json.dumps(structured, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        results.append(structured)

    if config.print_stats:
        print(render_stats(results))
    return results


def iter_pages(source_dir: Path, page_numbers: set[int] | None = None) -> Iterable[PageSource]:
    """Yield OCR page sources in numeric order."""
    pages: list[PageSource] = []
    for path in source_dir.glob("page-*/markdown.md"):
        match = PAGE_DIR_RE.search(str(path.parent.name))
        if not match:
            continue
        page_number = int(match.group(1))
        if page_numbers is not None and page_number not in page_numbers:
            continue
        pages.append(PageSource(page_number=page_number, markdown_path=path))
    return sorted(pages, key=lambda item: item.page_number)


def parse_page(page: PageSource, source_dir: Path = OCR_DIR) -> dict:
    """Parse a single OCR markdown page into a page-type specific JSON object."""
    raw_text = page.markdown_path.read_text(encoding="utf-8")
    all_lines = [line.rstrip() for line in raw_text.splitlines()]
    images = [match.group(2) for line in all_lines for match in IMAGE_RE.finditer(line)]
    lines = preprocess_lines(all_lines, page.page_number)
    text = "\n".join(lines)
    page_type = classify_page(page.page_number, lines, text)

    parser = {
        "title_page": parse_title_page,
        "study_guide": parse_study_guide_page,
        "front_matter": parse_front_matter,
        "table_of_contents": parse_table_of_contents,
        "vocabulary": parse_vocabulary_page,
        "exercise": parse_exercise_page,
        "column": parse_column_page,
        "summary": parse_summary_page,
        "index": parse_index_page,
        "raw": parse_raw_page,
    }.get(page_type, parse_raw_page)

    parsed = parser(page.page_number, lines)
    parsed.setdefault("page_number", page.page_number)
    parsed.setdefault("page_type", page_type)
    if images:
        parsed["source_images"] = images
    parsed["source_file"] = str(page.markdown_path.relative_to(ROOT))
    parsed["source_folder"] = str(page.markdown_path.parent.relative_to(ROOT))
    return parsed


def preprocess_lines(lines: list[str], page_number: int) -> list[str]:
    """Remove empty lines, page-number artifacts, and inline image markdown."""
    cleaned: list[str] = []
    for line in lines:
        line = line.replace("\u3000", " ").strip()
        if not line:
            continue
        if IMAGE_RE.search(line):
            continue
        if line == str(page_number):
            continue
        cleaned.append(line)
    return cleaned


def classify_page(page_number: int, lines: list[str], text: str) -> str:
    """Assign a coarse page type so layout-specific parsing can take over."""
    if page_number in (1, 2):
        return "title_page"
    if page_number in (3, 4):
        return "study_guide"
    if page_number in (5, 6, 7):
        return "table_of_contents"
    if "もくじ" in text or "CONTENTS" in text:
        return "table_of_contents"
    if sum(1 for line in lines if line.startswith("Unit ")) >= 2 or "もくじ" in text or "CONTENTS" in text:
        return "table_of_contents"
    if "語彙索引" in text and "Unit " not in text:
        return "index"
    if count_entry_starts(lines) >= 3:
        return "vocabulary"
    if "練習問題" in text or any(ROMAN_SECTION_RE.match(line) for line in lines):
        return "exercise"
    if "コラム" in text:
        return "column"
    if "まとめ" in text and count_entry_starts(lines) < 3:
        return "summary"
    if page_number <= 7:
        return "front_matter"
    return "raw"


def count_entry_starts(lines: list[str]) -> int:
    count = 0
    for line in lines:
        if is_vocab_entry_start(line):
            count += 1
    return count


def is_vocab_entry_start(line: str) -> bool:
    match = ENTRY_START_RE.match(line)
    if not match:
        return False
    rest = match.group(2)
    first_token = rest.split()[0] if rest.split() else ""
    if not re.search(r"[ぁ-ゖァ-ヴー]", first_token):
        return False
    if "⇔" in rest:
        return False
    if re.match(r"[a-dＡ-Ｄ]\s", rest):
        return False
    if re.match(r"[IVXⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+\b", match.group(1)):
        return False
    return True


def parse_front_matter(page_number: int, lines: list[str]) -> dict:
    """Capture early pages that are mostly prose rather than structured entries."""
    headings: list[str] = []
    paragraphs: list[str] = []
    for line in lines:
        if line.startswith("#"):
            headings.append(line.lstrip("#").strip())
        else:
            paragraphs.append(line)

    return {
        "page_number": page_number,
        "page_type": "front_matter",
        "headings": headings,
        "paragraphs": paragraphs,
        "raw_text": "\n".join(lines),
    }


def parse_title_page(page_number: int, lines: list[str]) -> dict:
    """Parse title pages while keeping raw OCR text for traceability."""
    headings = [strip_markdown(line) for line in lines if line.startswith("#")]
    body = [strip_markdown(line) for line in lines if not line.startswith("#")]
    title = " ".join(part for part in headings if "耳から覚える" in part or "語彙トレーニング" in part).strip()
    subtitle = next((part for part in headings if "意味" in part or "理解" in part), None)
    return {
        "page_number": page_number,
        "page_type": "title_page",
        "title": title or None,
        "headings": headings,
        "subtitle": subtitle,
        "content": body,
        "raw_text": "\n".join(lines),
    }


def parse_study_guide_page(page_number: int, lines: list[str]) -> dict:
    """Parse the introduction/study-guide pages into title and sections."""
    title = strip_markdown(lines[0]) if lines else None
    sections: list[dict] = []
    current: dict | None = None
    intro: list[str] = []

    for line in lines[1:]:
        normalized = strip_markdown(line)
        if not normalized:
            continue
        if line.startswith("##") or line.startswith("#"):
            current = {"heading": normalized, "points": []}
            sections.append(current)
            continue
        if re.match(r"^\d+[\. ]", normalized) or normalized.startswith(("※", "①", "②", "③", "④", "⑤", "⑥")):
            target = current["points"] if current is not None else intro
            target.append(normalized)
        else:
            target = current["points"] if current is not None else intro
            target.append(normalized)

    result = {
        "page_number": page_number,
        "page_type": "study_guide",
        "title": title,
        "sections": sections,
        "raw_text": "\n".join(lines),
    }
    if intro:
        result["intro"] = intro
    return result


def parse_table_of_contents(page_number: int, lines: list[str]) -> dict:
    """Parse contents pages into unit/group entries where the OCR is reliable enough."""
    entries: list[dict] = []
    current_unit: dict | None = None
    pending_misc: list[str] = []

    for line in lines:
        compact = normalize_spaces(strip_markdown(line))
        if not compact or compact in {"Step 1 2 3 4", "5", "6"} or compact.startswith("⭕️"):
            continue
        if compact.startswith("本書で勉強する方へ"):
            entries.append({"type": "guide", "title": "本書で勉強する方へ", "page": extract_last_number(compact)})
            continue
        unit_match = re.search(
            r"Unit\s*(\d+)\s+(.+?)\s+(\d+\s*[～~]\s*\d+).+?(\d+)$",
            compact,
        )
        if unit_match:
            current_unit = {
                "type": "unit",
                "unit": int(unit_match.group(1)),
                "title": unit_match.group(2).strip(),
                "range": unit_match.group(3).replace(" ", ""),
                "start_page": int(unit_match.group(4)),
                "items": [],
            }
            entries.append(current_unit)
            pending_misc = []
            continue

        summary_match = re.search(
            r"まとめ\s*(\d+)\s+(.+?)\s+(\d+\s*[～~]\s*\d+).+?(\d+)$",
            compact,
        )
        if summary_match:
            entries.append(
                {
                    "type": "summary",
                    "summary": int(summary_match.group(1)),
                    "title": summary_match.group(2).strip(),
                    "range": summary_match.group(3).replace(" ", ""),
                    "page": int(summary_match.group(4)),
                }
            )
            continue

        appendix_match = re.search(r"(語彙索引|解答)\s+(\d+)$", compact)
        if appendix_match:
            entries.append({"type": "appendix", "title": appendix_match.group(1), "page": int(appendix_match.group(2))})
            continue

        if current_unit is not None:
            item = parse_toc_item(compact)
            if item is not None:
                current_unit["items"].append(item)
                continue
            pending_misc.append(compact)

    result = {
        "page_number": page_number,
        "page_type": "table_of_contents",
        "title": "もくじ" if "もくじ" in "\n".join(lines) else "CONTENTS",
        "entries": entries,
        "raw_text": "\n".join(lines),
    }
    if pending_misc:
        result["unparsed_lines"] = pending_misc
    return result


def parse_vocabulary_page(page_number: int, lines: list[str]) -> dict:
    """Parse core vocabulary pages into entry blocks and optional trailing sections."""
    metadata, content_lines = extract_common_metadata(lines)
    vocab_lines, trailing_lines = split_vocabulary_and_trailing(content_lines)
    blocks = split_blocks(vocab_lines, is_vocab_entry_start)
    vocabulary = [parse_vocabulary_block(block) for block in blocks if block]
    result = {
        "page_number": page_number,
        "page_type": "vocabulary",
        "metadata": metadata,
        "vocabulary": vocabulary,
    }
    if trailing_lines:
        result["trailing_content"] = [strip_markdown(line) for line in trailing_lines]
        column = parse_trailing_column(trailing_lines)
        if column is not None:
            result["column"] = column
    return result


def parse_vocabulary_block(block: list[str]) -> dict:
    """Parse one numbered vocabulary entry block."""
    header = strip_markdown(block[0])
    match = ENTRY_START_RE.match(header)
    assert match is not None

    entry_id = int(match.group(1))
    rest = match.group(2).strip()
    head_part, translations = split_translations(rest)
    head_tokens = head_part.split()
    remaining_lines = list(block[1:])

    reading_kana = head_tokens[0] if head_tokens else None
    surface_raw = " ".join(head_tokens[1:]) if len(head_tokens) > 1 else None
    if surface_raw is None and remaining_lines:
        headword_hint = extract_headword_hint_line(remaining_lines[0], reading_kana)
        if headword_hint is not None:
            surface_raw = headword_hint
            remaining_lines.pop(0)
    surface_raw, inline_en = split_inline_english_gloss(surface_raw)
    if inline_en:
        translations = merge_translations(inline_en, translations)
    kanji, word_type = extract_surface_and_type(surface_raw, reading_kana)
    relation_headword = kanji or surface_raw or reading_kana

    entry: dict[str, object] = {
        "id": entry_id,
        "reading_kana": reading_kana,
    }
    if kanji:
        entry["kanji"] = kanji
    if surface_raw and surface_raw != kanji:
        entry["headword_raw"] = surface_raw
    if word_type:
        entry["type"] = word_type
    if translations:
        entry["translations"] = translations

    senses: list[dict] = []
    loose_examples: list[str] = []
    loose_relations: list[str] = []
    notes: list[str] = []
    current_sense: dict | None = None

    for line in remaining_lines:
        normalized = strip_markdown(line)
        if not normalized:
            continue

        if translations is None and is_translation_only_line(normalized):
            fallback_translations, _ = extract_translation_notes([normalized])
            if fallback_translations:
                translations = fallback_translations
                entry["translations"] = translations
                continue

        sense_match = re.match(r"^([①-⑳])\s*(.*)$", normalized)
        if sense_match:
            current_sense = {"label": sense_match.group(1)}
            remainder = sense_match.group(2).strip()
            if remainder:
                current_sense["content"] = split_example_fragments(remainder)
            senses.append(current_sense)
            continue

        if is_relation_line(normalized):
            relation_blocks = parse_relation_line(normalized, relation_headword)
            if current_sense is not None:
                current_sense.setdefault("relation_blocks", []).extend(relation_blocks)
            else:
                loose_relations.extend(relation_blocks)
            continue

        if is_example_like_line(normalized):
            examples = split_example_fragments(normalized)
            if current_sense is not None:
                current_sense.setdefault("examples", []).extend(examples)
            else:
                loose_examples.extend(examples)
            continue

        if current_sense is not None:
            current_sense.setdefault("notes", []).append(normalized)
        else:
            notes.append(normalized)

    if translations is None:
        fallback_translations, notes = extract_translation_notes(notes)
        if fallback_translations:
            translations = fallback_translations
            entry["translations"] = translations

    if senses:
        entry["senses"] = senses
    if loose_examples:
        entry["examples"] = loose_examples
    if loose_relations:
        entry["relation_blocks"] = loose_relations
    if notes:
        entry["notes"] = notes

    return entry


def parse_exercise_page(page_number: int, lines: list[str]) -> dict:
    """Parse exercise pages into sections, subsections, and questions."""
    metadata, content_lines = extract_common_metadata(lines)
    sections: list[dict] = []
    current_section: dict | None = None
    option_buffer: list[str] = []

    for raw_line in content_lines:
        line = strip_markdown(raw_line)
        if not line:
            continue

        roman_match = ROMAN_SECTION_RE.match(line)
        if roman_match:
            current_section = {
                "id": roman_match.group(1),
                "instruction": roman_match.group(2).strip(),
                "questions": [],
            }
            sections.append(current_section)
            option_buffer = []
            continue

        subsection_match = SUBSECTION_RE.match(line)
        if subsection_match:
            current_section = current_section or {"questions": []}
            current_section.setdefault("subsections", []).append(
                {"id": subsection_match.group(1), "questions": [], "options": []}
            )
            option_buffer = []
            continue

        question_match = QUESTION_RE.match(line)
        if question_match:
            target = current_section
            if target and target.get("subsections"):
                target = target["subsections"][-1]
            if target is None:
                current_section = {"questions": []}
                sections.append(current_section)
                target = current_section
            target.setdefault("questions", []).append(
                {"id": int(question_match.group(1)), "text": question_match.group(2).strip()}
            )
            continue

        if line.startswith("|"):
            option_buffer.extend(parse_markdown_table_options([raw_line]))
            continue

        if re.match(r"^[a-dＡ-Ｄ]\s", line):
            target = current_section
            if target and target.get("subsections"):
                target = target["subsections"][-1]
            if target is not None and target.get("questions"):
                target["questions"][-1].setdefault("choices", []).append(line)
            continue

        if current_section is None:
            metadata.setdefault("headers", []).append(line)
            continue

        target = current_section
        if target.get("subsections"):
            target = target["subsections"][-1]

        if option_buffer:
            target.setdefault("options", []).extend(option_buffer)
            option_buffer = []

        section_id = current_section.get("id") if current_section is not None else None
        if section_id in {"Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "II", "III", "IV", "V"}:
            target.setdefault("term_list", []).extend(line.split())
        else:
            target.setdefault("notes", []).append(line)

    if option_buffer and sections:
        target = sections[-1]
        if target.get("subsections"):
            target = target["subsections"][-1]
        target.setdefault("options", []).extend(option_buffer)

    return {
        "page_number": page_number,
        "page_type": "exercise",
        "metadata": metadata,
        "sections": sections,
    }


def parse_column_page(page_number: int, lines: list[str]) -> dict:
    """Parse standalone column pages into title plus body lines."""
    metadata, content_lines = extract_common_metadata(lines)
    title = next((strip_markdown(line) for line in content_lines if line.startswith("#")), None)
    body_lines = [strip_markdown(line) for line in content_lines if not line.startswith("#")]
    return {
        "page_number": page_number,
        "page_type": "column",
        "metadata": metadata,
        "title": title,
        "content": [line for line in body_lines if line],
        "raw_text": "\n".join(content_lines),
    }


def parse_summary_page(page_number: int, lines: list[str]) -> dict:
    """Parse summary pages using the same entry grammar as vocabulary pages."""
    metadata, content_lines = extract_common_metadata(lines)
    blocks = split_blocks(content_lines, is_vocab_entry_start)
    items = [parse_vocabulary_block(block) for block in blocks if block]
    title = next((strip_markdown(line) for line in content_lines if "まとめ" in line), None)
    return {
        "page_number": page_number,
        "page_type": "summary",
        "metadata": metadata,
        "title": title,
        "items": items,
        "raw_text": "\n".join(content_lines),
    }


def parse_index_page(page_number: int, lines: list[str]) -> dict:
    """Keep index pages simple and lossless."""
    return {
        "page_number": page_number,
        "page_type": "index",
        "entries": [strip_markdown(line) for line in lines],
        "raw_text": "\n".join(lines),
    }


def parse_raw_page(page_number: int, lines: list[str]) -> dict:
    """Fallback parser for pages that do not match a known layout confidently."""
    metadata, content_lines = extract_common_metadata(lines)
    return {
        "page_number": page_number,
        "page_type": "raw",
        "metadata": metadata,
        "content": [strip_markdown(line) for line in content_lines],
        "raw_text": "\n".join(content_lines),
    }


def extract_common_metadata(lines: list[str]) -> tuple[dict, list[str]]:
    """Strip repeated page-level headers before content-specific parsing."""
    metadata: dict[str, object] = {}
    content_lines = list(lines)

    if content_lines:
        match = SECTION_CODE_RE.match(content_lines[0])
        if match:
            metadata["section_code"] = match.group(1)
            content_lines.pop(0)

    if content_lines and content_lines[0].startswith("Unit "):
        metadata["unit_header"] = content_lines.pop(0)

    if content_lines and re.match(r"^\d+[～~]\d+$", content_lines[0]):
        metadata["range"] = content_lines.pop(0)

    if content_lines and "練習問題" in content_lines[0]:
        metadata["exercise_title"] = content_lines.pop(0)

    if content_lines and content_lines[0].startswith("Step "):
        metadata["step_header"] = content_lines.pop(0)

    return metadata, content_lines


def split_blocks(lines: list[str], start_predicate) -> list[list[str]]:
    """Split a page into blocks whenever a new entry start is detected."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if start_predicate(line):
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks


def render_stats(pages: list[dict]) -> str:
    """Return a compact multi-line summary of parsed page counts by type."""
    counts: dict[str, int] = {}
    for page in pages:
        page_type = str(page.get("page_type", "unknown"))
        counts[page_type] = counts.get(page_type, 0) + 1

    summary_lines = [f"Parsed {len(pages)} pages"]
    for page_type in sorted(counts):
        summary_lines.append(f"- {page_type}: {counts[page_type]}")
    return "\n".join(summary_lines)


def parse_toc_item(compact: str) -> dict | None:
    column_match = re.search(r"コラム\s*(\d+)\s+(.+?)\s+(\d+)$", compact)
    if column_match:
        return {
            "type": "column",
            "id": int(column_match.group(1)),
            "title": column_match.group(2).strip(),
            "page": int(column_match.group(3)),
        }

    exercise_match = re.search(r"(練習問題[ⅠII]+|練習問題Ⅱ|練習問題II|練習問題I)\s+(.+?)\s+(\d+)$", compact)
    if exercise_match:
        return {
            "type": "exercise",
            "title": exercise_match.group(1),
            "range": exercise_match.group(2).strip().replace("...", "").strip(),
            "page": int(exercise_match.group(3)),
        }

    summary_match = re.search(r"まとめ\s*(\d+)\s+(.+?)\s+(\d+\s*[～~]\s*\d+).+?(\d+)$", compact)
    if summary_match:
        return {
            "type": "summary",
            "id": int(summary_match.group(1)),
            "title": summary_match.group(2).strip(),
            "range": summary_match.group(3).replace(" ", ""),
            "page": int(summary_match.group(4)),
        }

    return None


def extract_last_number(text: str) -> int | None:
    matches = re.findall(r"(\d+)", text)
    return int(matches[-1]) if matches else None


def split_vocabulary_and_trailing(lines: list[str]) -> tuple[list[str], list[str]]:
    vocab_lines: list[str] = []
    trailing_lines: list[str] = []
    in_trailing = False

    for line in lines:
        normalized = strip_markdown(line)
        is_section_boundary = (
            (
                normalized.startswith("コラム")
                or normalized.startswith("練習問題")
                or normalized.startswith("まとめ")
            )
            and not is_vocab_entry_start(normalized)
        )
        if is_section_boundary:
            in_trailing = True

        if in_trailing:
            trailing_lines.append(line)
        else:
            vocab_lines.append(line)

    return vocab_lines, trailing_lines


def split_translations(rest: str) -> tuple[str, dict | None]:
    separators = ["／", " / ", "/"]
    split_index = -1
    separator = None
    for candidate in separators:
        idx = rest.find(candidate)
        if idx != -1 and (split_index == -1 or idx < split_index):
            split_index = idx
            separator = candidate
    if split_index == -1 or separator is None:
        return rest, None

    head = rest[:split_index].strip()
    translation_text = rest[split_index:].strip(" ／/")
    parts = [part.strip() for part in re.split(r"\s*／\s*|\s*/\s*", translation_text) if part.strip()]
    translations: dict[str, str] = {}
    if parts:
        translations["zh"] = parts[0]
    return head, translations or None


def split_inline_english_gloss(surface_raw: str | None) -> tuple[str | None, str | None]:
    if not surface_raw:
        return surface_raw, None

    match = LATIN_GLOSS_RE.match(surface_raw)
    if not match:
        return surface_raw, None
    return match.group("surface").strip(), match.group("gloss").strip()


def extract_headword_hint_line(line: str, reading_kana: str | None) -> str | None:
    normalized = strip_markdown(line)
    if not normalized or " " in normalized:
        return None
    if reading_kana and normalized == reading_kana:
        return None
    if not re.search(r"[ぁ-ゖァ-ヴー一-龯]", normalized):
        return None

    candidate = normalized
    for raw_prefix, normalized_prefix in (("9", "ヲ"), ("ヨ", "ヲ")):
        if candidate.startswith(raw_prefix) and len(candidate) > 1:
            candidate = normalized_prefix + candidate[1:]
            break
    return candidate


def merge_translations(inline_en: str | None, translations: dict | None) -> dict | None:
    if not inline_en and not translations:
        return None
    merged = dict(translations or {})
    if inline_en:
        merged = {"en": inline_en, **merged}
    return merged


def extract_surface_and_type(surface_raw: str | None, reading_kana: str | None) -> tuple[str | None, str | None]:
    if not surface_raw:
        return None, None

    word_type: str | None = None
    surface = surface_raw

    markers = []
    if surface.startswith(("ガ", "ヲ")):
        markers.append(surface[0])
        surface = surface[1:]

    for suffix in ("(ヲ)スル", "スル", "な", "ノ"):
        if surface.endswith(suffix):
            markers.append(suffix)
            surface = surface[: -len(suffix)]
            break

    surface = surface.strip()
    if markers:
        word_type = "".join(markers)
    elif surface_raw.endswith("な"):
        word_type = "ナ形"

    if reading_kana and surface == reading_kana:
        return None, word_type
    return surface or None, word_type


def is_relation_line(line: str) -> bool:
    if RELATION_LABEL_RE.search(line):
        return True
    return line.startswith(("問 ", "答 ", "■ ", "☐ ", "☑ "))


def is_example_like_line(line: str) -> bool:
    if is_translation_only_line(line):
        return False
    return line.startswith(("・", "-", "「", "『", "(", "（")) or "・" in line


def split_example_fragments(line: str) -> list[str]:
    normalized = strip_markdown(line)
    normalized = normalized.replace(" · ", "・")
    normalized = re.sub(r"^[・\-]\s*", "", normalized)
    parts = [part.strip() for part in re.split(r"\s*・\s*", normalized) if part.strip()]
    expanded: list[str] = []
    for part in parts:
        sentence_parts = [
            frag.strip()
            for frag in re.split(r"(?<=。)\s+(?=[「『（\(A-Za-zぁ-んァ-ン一-龯])", part)
            if frag.strip()
        ]
        expanded.extend(sentence_parts or [part])
    return expanded or [normalized]


def strip_markdown(line: str) -> str:
    line = re.sub(r"^#+\s*", "", line)
    line = re.sub(r"^\|\s*", "", line)
    line = re.sub(r"\s*\|$", "", line)
    line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
    return line.strip()


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_markdown_table_options(lines: list[str]) -> list[str]:
    options: list[str] = []
    for line in lines:
        if "---" in line:
            continue
        if "|" not in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        for cell in cells:
            if cell:
                options.append(cell)
    return options


def extract_surface_label(raw_label: str, content: str) -> tuple[str, str]:
    content = content.strip("　 ")
    label = raw_label
    if raw_label in {"間", "意"}:
        label = "連" if "_" in content or "～" in content or "ヲ" in content or "ガ" in content else "関"
    elif raw_label in {"会", "目", "台"}:
        label = "合"
    elif raw_label in {"■", "☐"}:
        label = "連" if "_" in content or "～" in content or "⇔" in content else "関"
    elif raw_label == "☑":
        label = "関"
    return label, RELATION_LABEL_MAP.get(label, label)


def parse_relation_line(line: str, headword: str | None = None) -> list[dict]:
    cleaned = normalize_spaces(line.replace("∞", " ⇔ "))
    matches = list(RELATION_LABEL_RE.finditer(cleaned))
    if not matches:
        normalized = expand_relation_placeholders(cleaned, headword)
        return [{"label_jp": None, "type": "note", "content": normalized, "items": [normalized]}]

    blocks: list[dict] = []
    for idx, match in enumerate(matches):
        raw_label = match.group(1)
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(cleaned)
        raw_content = cleaned[start:end].strip("　 ")
        if not raw_content:
            continue
        label_jp, relation_type = extract_surface_label(raw_label, raw_content)
        content = expand_relation_placeholders(raw_content, headword)
        blocks.append(
            {
                "marker": raw_label,
                "label_jp": label_jp,
                "type": relation_type,
                "content": content,
                "items": split_relation_items(content),
            }
        )
    return blocks


def split_relation_items(content: str) -> list[str]:
    interim = content.replace("⇔", "、").replace("・", "、").replace("/", "／")
    parts = [part.strip() for part in re.split(r"[、,]\s*", interim) if part.strip()]
    return parts or [content]


def expand_relation_placeholders(content: str, headword: str | None) -> str:
    if not headword:
        return content
    return re.sub(r"[_＿～〜]+", headword, content)


def extract_translation_notes(notes: list[str]) -> tuple[dict | None, list[str]]:
    remaining: list[str] = []
    translations: dict | None = None
    for note in notes:
        candidate = note.lstrip("■☐☑ ").strip()
        if translations is None and TRANSLATION_ONLY_RE.match(candidate):
            parts = [part.strip() for part in re.split(r"\s*／\s*|\s*/\s*", candidate) if part.strip()]
            mapped: dict[str, str] = {}
            if parts and re.search(r"[A-Za-z]", parts[0]):
                mapped["en"] = parts[0]
                if len(parts) > 1:
                    mapped["zh"] = parts[1]
            elif parts:
                mapped["zh"] = parts[0]
            if mapped:
                translations = mapped
                continue
        remaining.append(note)
    return translations, remaining


def is_translation_only_line(line: str) -> bool:
    compact = line.lstrip("■☐☑ ").strip()
    return bool(TRANSLATION_ONLY_RE.match(compact) and ("／" in compact or "/" in compact))


def parse_trailing_column(lines: list[str]) -> dict | None:
    stripped = [strip_markdown(line) for line in lines if strip_markdown(line)]
    if not stripped or not stripped[0].startswith("コラム"):
        return None

    header_cells = [cell.strip() for cell in stripped[0].split("|") if cell.strip()]
    title = header_cells[1] if len(header_cells) > 1 else stripped[0]
    subtitle = header_cells[2] if len(header_cells) > 2 else None
    rows: list[list[str]] = []
    for line in stripped[2:]:
        if line.startswith("---"):
            continue
        cells = [cell.strip() for cell in line.split("|") if cell.strip()]
        rows.append(cells or [line])
    return {
        "title": title,
        "subtitle": subtitle,
        "rows": rows,
    }


if __name__ == "__main__":
    main()
