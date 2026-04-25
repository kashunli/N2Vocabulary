# N2 Vocabulary OCR Parser

This project converts OCR markdown from the N2 vocabulary book into page-level structured JSON. The workspace is now organized around three responsibilities:

- source data in [`ocr/pages`](ocr/pages)
- parser and pipeline code in [`scripts`](scripts)
- generated parser output in [`structured`](structured)

The [`sample`](sample) folder remains a style reference only. It is not parser input.

## Layout

```text
parse/
├── README.md
├── docs/
│   ├── handoff.md
│   ├── parse-guide.md
│   └── project-structure.md
├── scripts/
│   ├── parse_book.py
│   ├── build_vocab_audio_dataset.py
│   ├── audit_review_candidates.py
│   └── build_anki_deck.py
├── ocr/pages/               # OCR markdown, one folder per book page
├── structured/              # generated JSON output
├── sample/                  # schema/style examples only
└── pages_8_15_schema/       # extra schema notes for early pages
```

## Quick Start

Run the full parser:

```bash
python3 scripts/parse_book.py
```

Run with cleanup and a summary:

```bash
python3 scripts/parse_book.py --clean --stats
```

Parse only selected pages while tuning heuristics:

```bash
python3 scripts/parse_book.py --page 22 --page 146 --stats
```

Build the combined vocabulary JSON plus audio alignment manifests:

```bash
python3 scripts/build_vocab_audio_dataset.py
```

Skip audio work and only write the combined vocabulary dataset:

```bash
python3 scripts/build_vocab_audio_dataset.py --skip-audio
```

Build the Anki exports and packaged deck from the combined vocabulary dataset:

```bash
python3 scripts/build_anki_deck.py
```

## Workflow

1. Read OCR source under [`ocr/pages`](ocr/pages).
2. Check the target schema and parsing rules in [`docs/parse-guide.md`](docs/parse-guide.md).
3. Update parser logic in [`scripts/parse_book.py`](scripts/parse_book.py).
4. Regenerate JSON into [`structured`](structured).
5. Inspect pages with OCR noise and preserve uncertainty in fields like `notes`, `trailing_content`, `unparsed_lines`, or `raw_text` instead of discarding content.
6. Run [`scripts/build_vocab_audio_dataset.py`](scripts/build_vocab_audio_dataset.py) to flatten vocabulary entries from [`../json`](../json), align them to [`../audio`](../audio), and generate clip manifests under [`../output`](../output).

## Current Output Snapshot

The current dataset covers 287 parsed pages.

- `title_page`: 2
- `study_guide`: 2
- `table_of_contents`: 5
- `vocabulary`: 163
- `exercise`: 75
- `column`: 12
- `summary`: 2
- `index`: 1
- `raw`: 25

## Documentation

- [`docs/project-structure.md`](docs/project-structure.md): directory map and maintenance notes
- [`docs/parse-guide.md`](docs/parse-guide.md): canonical parsing rules and schema guidance
- [`docs/handoff.md`](docs/handoff.md): current quality notes and next improvement targets
- [`docs/vocab-audio-pipeline.md`](docs/vocab-audio-pipeline.md): implementation notes for the combined vocabulary and audio-clipping pipeline, including decisions, tradeoffs, and debugging history
- [`docs/anki-deck-pipeline.md`](docs/anki-deck-pipeline.md): Anki deck structure, export formats, card templates, and packaging notes

## Notes

- Everything in [`structured`](structured) is derived from [`ocr/pages`](ocr/pages).
- The parser is heuristic-based and intentionally conservative when OCR is ambiguous.
- Some table-of-contents pages, mixed layout pages, and image-heavy pages still need better heuristics or manual review.
