# Vocabulary Items Migration Plan

## Summary

Migrate `wordService` from book-scoped `entries` as the conceptual core to
canonical `vocabulary_items` with one-to-many `book_entries` placements. The
first pass is conservative: exact normalized `(kanji, reading)` matches share a
canonical item automatically, while ambiguous candidates are reported rather
than merged.

## Decisions

- `vocabulary_items` is the canonical table name because rows may be words,
  compounds, expressions, adverbs, idioms, or related learnable terms.
- Existing `entry_id` remains the browser/API placement identifier for
  compatibility; new `item_id` is the internal shared vocabulary identifier.
- `book_entries` owns book placement: `book_code`, `unit_number`,
  `source_index`, and `position`.
- `item_examples` is authoritative for examples, main sentences, related terms,
  and example audio.
- `item_marks` is item-level, so known/flagged progress is shared across book
  views.
- Old `entries`, `entry_examples`, `word_marks`, and provenance tables remain
  during the first pass for comparison and rollback confidence.

## Implementation Shape

- Add migration `007_vocabulary_items.sql`.
- Populate canonical items by exact normalized `TRIM(kanji)` and
  `TRIM(reading)`.
- Deduplicate item examples by normalized `(kind, text, reading,
  translation_zh, category)`, preserving deterministic display order.
- Copy sentence stars, marks, audio paths, and provenance to item-based tables.
- Update Rust and Python read paths to prefer canonical tables while keeping
  API output stable.
- Extend validation to report old-vs-new counts, exact merge groups, ambiguous
  candidates, and conflicts.

## Verification

- Back up `wordService/data/n2vocab.sqlite` before applying the migration.
- Run `python db/migrate.py --db wordService/data/n2vocab.sqlite`.
- Run `python tools/validate_db_manifest.py --db wordService/data/n2vocab.sqlite`.
- Run Rust checks from `wordService/rust`: `cargo fmt --check`, `cargo test`.
- Run Python tests from repo root:
  `python -m unittest tools.test_import_n2_must_1500 tools.test_import_green_word_book tools.test_merge_gwb_duplicates`.
- Smoke `/api/books`, `/api/entries?book=N2&state=all&search=`,
  `/api/entries?book=N3&state=all&search=`, and a duplicate word across books.
