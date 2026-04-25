# Handoff Notes

The current parser implementation lives in [`../scripts/parse_book.py`](../scripts/parse_book.py).

## What Was Done

A parser was added in [`../scripts/parse_book.py`](../scripts/parse_book.py) and used to generate [`../structured`](../structured) from [`../ocr/pages`](../ocr/pages).

The main correction from the previous pass was removing any dependence on `sample` as input. `sample` now serves only as a schema/style reference.

## Current State

Good enough:

- Full-page export exists for all 287 OCR pages
- Early front matter is included and OCR-derived
- Many vocabulary pages are split into entries with IDs, readings, examples, and relation-like lines
- Exercise pages are separated into sections and questions

Still rough:

- Table-of-contents pages are only partially normalized
- OCR noise often leaks into `kanji`, `translations`, and `notes`
- Mixed pages that switch from vocabulary to column content are only partially segmented
- Image-heavy pages often fall back to `raw`

## Most Important Files

- [`../scripts/parse_book.py`](../scripts/parse_book.py)
- [`../structured/page_005.json`](../structured/page_005.json)
- [`../structured/page_006.json`](../structured/page_006.json)
- [`../structured/page_007.json`](../structured/page_007.json)
- [`../structured/page_022.json`](../structured/page_022.json)
- [`../structured/page_146.json`](../structured/page_146.json)

## Recommended Next Steps

1. Improve contents parsing.
The current regexes handle simple lines but do not fully normalize markdown-table rows like pages 5 and 7.

2. Improve vocabulary header parsing.
Some OCR lines combine the headword, grammatical marker, and translation text in ways that currently pollute `kanji` or `type`.

3. Add page-level override rules.
Several layouts recur by section. A small map of page ranges or unit-specific parsers would likely improve quality quickly.

4. Normalize exercise option tables.
Some exercise pages keep choice tables in `notes` instead of `options`.

5. Decide whether to keep `raw_text` everywhere.
It is useful for traceability, but if the target dataset should be cleaner, this can be made optional.

## Quick Regeneration

```bash
find structured -type f -delete
python3 scripts/parse_book.py
```

## Assumptions

- Losing some fine-grained structure is acceptable if the OCR does not reliably support it
- Preserving all source content is more important than forcing every page into an overconfident schema
- The sample folder demonstrates the desired style, but not the exact book or exact field set for every page
