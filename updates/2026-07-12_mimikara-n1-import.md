# 2026-07-12 - Mimikara N1 import

## Why

The reviewed `minikaraWordN1` canonical vocabulary and cut audio needed to be
available through the existing multi-book web service and Anki workflow without
overwriting shared N2/N3 content or modifying the source project.

## What changed

- Added `tools/import_mimikara_n1.py`, a resumable importer that validates the
  complete 1,170-entry source dataset and its accepted 2,340 audio clips.
- Imported the book as `N1` with 14 units. Unit placement comes from the
  accepted audio track manifest, which also avoids seven incorrect unit values
  found in the source canonical JSON.
- Reused 201 exact shared vocabulary identities on the first import and added
  969 new shared items. All N1 meanings, usage notes, related forms, source
  locations, examples, and provenance remain attached to the N1 book records.
- Added per-book word-audio, verb-pattern, and meaning overrides to
  `book_entries`. This prevents an imported book appearance from replacing the
  existing shared N2/N3 card data.
- Copied reviewed audio to stable ASCII paths under `clips/n1/words/` and
  `clips/n1/sentences/`. Source audio and source review evidence were read-only.
- Updated the Rust repository, SQLite compatibility loader, and Anki builder to
  prefer book-specific values while retaining fallbacks for existing books.
- For shared N1/N2/N3 identities, the N1 view uses its book-specific word audio
  and promotes the N1 source sentence to the first/main example. Other book
  views retain their own main sentence and audio selection.
- Converted 3,221 N1 compounds, collocations, synonyms, antonyms, related
  concepts, and idioms from Markdown lists into individual `related_term`
  records with source provenance. The web UI and Anki render readable category
  labels, and Anki preserves every term instead of truncating long lists.
- Added `tools/translate_n1_examples_en.py`, a resumable DeepSeek
  `deepseek-v4-flash` workflow with strict ID/order validation, parallel
  large-batch generation, cached review files, and guarded database apply.
  English is complete for all 3,211 N1 sentence rows and all 3,221 structured
  terms. The importer preserves these translations on future reruns.
- Built `output/N1Words.apkg` with stable book-scoped note identities.

A pre-import database backup is preserved at
`wordService/data/n2vocab.sqlite.backup_before_n1_import_20260712_223033`.
The structured-term pass also has a dedicated backup at
`wordService/data/n2vocab.sqlite.backup_before_n1_structured_terms_20260712_2300`.

## Validation

- Isolated 10-entry pilot: 10 notes, 20 required media files, and successful
  API/detail/audio HTTP checks.
- Full database: 1,170 N1 entries, indices exactly 1 through 1,170, 14 units,
  3,211 provenance-linked examples, all required clip fields populated,
  `PRAGMA integrity_check = ok`, and zero foreign-key violations.
- All 2,340 imported MP3 files match the accepted source files by SHA-256.
- Existing non-N1 legacy vocabulary rows, book-entry counts, word marks, and
  sentence stars match the pre-import backup.
- Rust: `cargo test` passed, including 21 repository tests.
- Python: `python -m unittest discover -s tools -p 'test_*.py'` passed 14 tests.
- Live API: N1 book/unit/list/search/detail routes and both word and sentence
  audio returned expected data and HTTP 200 responses.
- Anki: `output/N1Words.apkg` contains 1,170 unique notes/cards and 2,590 media
  files; every required word and main-sentence sound reference resolves.

## Residual notes

Shared identities continue to share normalized extra examples through the
existing `item_examples` model, with `item_example_sources` recording N1
provenance. The book-specific main card fields and audio remain isolated.

The general database manifest validator still reports two pre-existing N3
main-sentence compatibility mismatches. The N1 import did not change those rows.
