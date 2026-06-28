# 2026-06-22 - N2 must-1500 PDF import

## Why

`N2必背1500词（PDF版）.pdf` needed to become a normal selectable book in the
existing SQLite-backed wordService. Although the PDF text is selectable,
Poppler and pypdf misdecode its embedded Japanese font. PyMuPDF reads the same
text layer correctly, so OCR is neither needed nor used by the shipped flow.

The title says 1500 words, while the document itself contains 1,488 structured
entry blocks across 177 pages. The importer validates that exact count rather
than silently padding or dropping rows.

## What changed

- Added `tools/import_n2_must_1500.py`, the single extraction/import entrypoint.
- Added `data/n2_must_1500_vocab.json`, the human-auditable extracted artifact.
- Added `tools/test_import_n2_must_1500.py` for page-break parsing, source-shape
  normalization, and idempotent SQLite import.
- Imported the data as book code `N2_1500`, title `N2 必背1500词`.
- Mapped the book's nine parts to service units: nouns, verbs, i-adjectives,
  na-adjectives, adnominals, adverbs, conjunctions, affixes, and loanwords.
- Preserved accent, part of speech, source form, and related forms in the detail
  notes. The PDF has no example-sentence field, so the import does not invent one.

## Rerun

Install the extraction dependency once if needed:

```powershell
python -m pip install PyMuPDF
```

Regenerate and audit the JSON without touching SQLite:

```powershell
python tools\import_n2_must_1500.py --extract-only
python -m unittest tools.test_import_n2_must_1500
```

Import the reviewed JSON and back up SQLite first:

```powershell
python tools\import_n2_must_1500.py --import-only --backup
```

The importer is idempotent by `(book_code, source_index)`.

## Verification

- Extracted entries: `1488`; blank headword/POS/Chinese meaning: `0`.
- Section counts: nouns `912`, verbs `265`, i-adjectives `34`, na-adjectives
  `82`, adnominals `7`, adverbs `95`, conjunctions `13`, affixes `15`, loanwords `65`.
- SQLite `PRAGMA integrity_check`: `ok`; `PRAGMA foreign_key_check`: no rows.
- Isolated service smoke on port `8785`: `/api/books` listed `N2_1500`, its
  summary returned 1,488 entries and nine units, and search returned `愛情`.
- Pre-import backup:
  `wordService/data/n2vocab.sqlite.backup_before_n2_1500_import_20260622_204704`.
