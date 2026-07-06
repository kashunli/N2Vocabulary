# N2 高频词汇550 Import

Imported `N2高频词汇550个-分类整理137972411420343518.1ea2d37c82ca89e.pdf` as a new
book in the shared wordService database.

## What changed

- Added `tools/import_n2_high_frequency_550.py`.
- Extracted the selectable PDF text into `data/n2_high_frequency_550_vocab.json`.
- Imported the source as `book_code = N2_HF_550`, title `N2 高频词汇550个`.
- Ignored all `出现次数` badge text during extraction.
- Used exact normalized `(headword, reading)` matching against
  `vocabulary_items`.
- Preserved all 550 source placements in `book_entries` and legacy `entries`.
- Reused 413 existing canonical items and created 137 new canonical items.
- Added 624 new canonical examples and reused 2 existing examples.

## Validation

- PDF extraction found 49 pages and exactly 550 contiguous entries.
- `出现次数` does not appear in the extracted JSON.
- Temporary DB import succeeded before live import.
- Idempotence check on the temporary DB added 0 items and 0 examples on rerun.
- Live DB import summary:
  - `book_entries = 550`
  - `legacy_entries = 550`
  - `integrity_check = ok`
  - `foreign_key_check_rows = 0`
- Live backup:
  `wordService/data/n2vocab.sqlite.backup_before_n2_hf_550_import_20260630_190824`

## Review artifacts

- Import summary: `output/n2_high_frequency_550_import_summary.json`
- Near-match report: `output/n2_high_frequency_550_near_matches.json`
