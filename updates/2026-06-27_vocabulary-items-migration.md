# Vocabulary Items Migration

## What Changed

- Added canonical `vocabulary_items` and `book_entries` tables in migration
  `007_vocabulary_items.sql`.
- Added item-level dependent tables: `item_examples`, `item_marks`,
  `item_sentence_stars`, `item_source_notes`, and `item_example_sources`.
- Kept legacy `entries`, `entry_examples`, `word_marks`, and provenance tables
  in place for compatibility and comparison.
- Updated the Rust service to read book views through `book_entries` joined to
  `vocabulary_items`, while keeping `entry_id` as the API placement ID.
- Updated mark, star, and generated-audio writes to target item-level tables.
- Updated `db.connect.load_entries()` to prefer the canonical manifest and fall
  back to legacy tables for older DB copies.
- Extended `tools/validate_db_manifest.py` to report canonical item counts and
  migration report summaries.

## Live DB Result

- Backup before migration:
  `wordService/data/n2vocab.sqlite.backup_before_vocabulary_items_20260627_195533`
- `book_entries`: 7459
- `vocabulary_items`: 6280
- `item_examples`: 10625
- `item_marks`: 1436
- `item_sentence_stars`: 26
- `item_source_notes`: 8383
- Exact merge report groups: 1160
- Ambiguous reports are preserved in `vocabulary_migration_reports`.

## Verification

- `python tools/validate_db_manifest.py --db wordService/data/n2vocab.sqlite`
  passed with `integrity_check: ok` and `foreign_key_check_rows: 0`.
- `cargo fmt --check` passed.
- `cargo test` passed using a temporary Cargo target directory to avoid a
  Windows file lock on the default debug executable.
- `python -m unittest tools.test_import_n2_must_1500 tools.test_import_green_word_book tools.test_merge_gwb_duplicates`
  passed.
- API smoke on port `8797` verified `/api/books`, N2/N3 entry listings, shared
  duplicate examples for `お喋り`, and an `N2_1500` related-term detail card.
