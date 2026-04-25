# Project Structure

## Purpose

This folder exists to turn OCR output from the N2 vocabulary book into structured JSON that can be cleaned further or imported into downstream study tooling.

## Directory Map

- [`../scripts`](../scripts): parser and pipeline CLIs
- [`../docs`](../docs): human-facing documentation and maintenance notes
- [`../ocr/pages`](../ocr/pages): OCR source, one folder per page, usually containing `markdown.md` and any extracted images
- [`../structured`](../structured): generated JSON output, one file per page
- [`../sample`](../sample): example JSON shape only
- [`../pages_8_15_schema`](../pages_8_15_schema): extra schema notes for early-page normalization

## Parser Responsibilities

[`../scripts/parse_book.py`](../scripts/parse_book.py) is responsible for:

- iterating OCR pages in numeric order
- classifying each page into a layout type
- applying layout-specific parsing heuristics
- preserving uncertain OCR content when exact normalization is unsafe
- writing `page_###.json` output

## Maintenance Rules

- Treat [`../ocr/pages`](../ocr/pages) as source input.
- Treat [`../structured`](../structured) as generated output.
- Do not use [`../sample`](../sample) as parser input.
- Prefer adding page-type heuristics over destructive cleanup when OCR is ambiguous.
- Keep schema assumptions aligned with [`parse-guide.md`](parse-guide.md).

## Useful Commands

Full regeneration:

```bash
python3 scripts/parse_book.py --clean --stats
```

Targeted debugging:

```bash
python3 scripts/parse_book.py --page 22 --stats
```

CLI help:

```bash
python3 scripts/parse_book.py --help
```
