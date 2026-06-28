# 2026-06-17 - GreenWordBook import

## Why

The GreenWordBook OCR project produced a structured N2 vocabulary JSON that should be browsable in the existing SQLite-backed `wordService`, alongside the current N2/N3 sources.

## What changed

- Added `tools/import_green_word_book.py` as the idempotent import entrypoint for `D:\n2Prepare\greenWordBook\data\green_word_book_n2_vocab.json`.
- Imported GreenWordBook as `book_code = GWB_N2` with title `无敌绿宝书 N2 词汇`.
- Used JSON order as `entries.source_index` because source `id` and `entry_number` values contain duplicates and malformed rows.
- Derived all 4763 record units from `material/page_manifest.json`, producing 41 wordService units.
- Preserved learner-facing GreenWordBook notes in `entries.explanation_md`, including synonyms, collocations, exam questions, and visible review markers. Source IDs, page numbers, section, bracket form, part of speech, and accent stay out of the detail panel because they are import bookkeeping rather than sentence explanations.
- The GWB detail panel labels retained learner content as `Study notes`; metadata-only entries omit the section entirely.
- Mapped every GWB `headword【display form】` pair into the service's normal two-field presentation. For example, `ice cream` is the main form and `アイスクリーム` is its visible reading, just as `相変わらず` pairs with `あいかわらず`.
- Normalized 128 source rows where OCR/parser output misplaced a bracketed display form in `reading` while leaving `bracket_form` empty. For example, entry `0046` now maps `reading: 【削る】` to `削る` / `けずる`.
- Wrote `output/green_word_book_import_summary.json` for audit.

## Results

- Imported records: 4763.
- Imported example sentences: 4408.
- Units imported: 41.
- Review-marked rows included: 7.
- Empty-field counts reported by the importer: 355 missing example sentences, 5 missing Chinese meanings, 2 missing headwords.

## Verification

- `python -m unittest tools.test_import_green_word_book`
- `python -m py_compile tools\import_green_word_book.py tools\test_import_green_word_book.py`
- Direct SQLite verification confirmed `GWB_N2` book, 4763 entries, 41 units, 4408 examples, and 7 visible `Needs review` markers.
- A follow-up check confirmed all 521 rows with non-kanji bracket forms now retain both source forms, including entry `0002` as `ice cream` / `アイスクリーム`; no pair mismatches remained.

## Notes

- A database backup was created before import: `wordService/data/n2vocab.sqlite.backup_before_green_word_book_import_20260617_215631`.
- A second backup was created before correcting loanword headwords: `wordService/data/n2vocab.sqlite.backup_before_gwb_headword_fix_20260618_191547`.
- The GreenWordBook source project was not mutated.
- No word audio was generated during import.
