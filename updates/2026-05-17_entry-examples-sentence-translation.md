# 2026-05-17 - Entry Example Sentence Normalization

## Why

The main example sentence was stored on the `entries` row as `sentence`,
`explanation_md`, and `sentence_clip`, while additional examples lived in
`entry_examples`. That made sentence-level translation, explanation, and audio
metadata hard to attach consistently.

## Decision

Normalize sentence-level learning content into `entry_examples`:

- `position = 0` is the main example sentence for the entry.
- `position = 1+` are the book's additional examples.
- `translation_en`, `translation_zh`, `explanation_md`, and `audio_clip` live
  on the example row.

The legacy `entries.sentence`, `entries.explanation_md`, and
`entries.sentence_clip` columns remain in the schema as compatibility fallback
fields. New project code should read the normalized `entry_examples` rows first.

## What Changed

- Added migration `db/migrations/002_entry_example_metadata.sql`.
- Updated `db/connect.py` so `load_entries()` reads the main sentence,
  sentence translations, explanation, and sentence audio from
  `entry_examples.position = 0`.
- Updated `db/import_vocabulary.py` so future imports write the main sentence as
  `entry_examples.position = 0` and shift JSON `examples` to `1+`.
- Added the one-time helper
  `updates/2026-05-17_entry_examples_sentence_translation.py`.
- Rebuilt word pages so example translations are visible on full pages and card
  detail views.

## Commands Run

```bash
python3 db/migrate.py
python3 updates/2026-05-17_entry_examples_sentence_translation.py --prepare-db --dry-run
python3 updates/2026-05-17_entry_examples_sentence_translation.py --limit 5 --batch-size 5
python3 updates/2026-05-17_entry_examples_sentence_translation.py --batch-size 30 --retries 5
python3 updates/2026-05-17_entry_examples_sentence_translation.py --batch-size 30 --apply-translations
python3 wordsAndExerciseInHtml/build_words.py
python3 wordsAndExerciseInHtml/build_word_cards.py
```

The Aliyun calls used `deepseek-v4-flash` through the repo-local
`skills/aliyun-openai-compatible-api/` contract and `DASHSCOPE_API_KEY` from the
environment or `~/.config/n2vocab/env`.

## Result

- `entry_examples` now has `3213` rows.
- `1159` main sentence rows were inserted at `position = 0`.
- Existing example rows were shifted to `position = 1+`.
- `3213` example rows received English and Simplified Chinese translations.
- Missing example translations after apply: `0`.
- `PRAGMA integrity_check`: `ok`.

Review artifacts live in `output/example_translation_2026-05-17/`:

- `selected_records.json`
- `selected_records_after_apply.json`
- `batch_0001.json` through `batch_0108.json`
- `all_translations.json`
- `manifest.json`
- `prepare_summary.json`
- `apply_summary.json`
- SQLite backups before row normalization and translation apply

## Notes

Aliyun occasionally returned malformed JSON. The helper retries malformed JSON
and incomplete row-count batches, and only writes a `batch_NNNN.json` file after
the batch has exactly the expected `(entry_id, position)` rows.

The Windows-mounted workspace still keeps stale `output/n2vocab.sqlite-wal` and
`output/n2vocab.sqlite-shm` sidecars locked sometimes. They were left in place
when deletion was denied; normal SQLite reads and integrity checks passed after
the copy-back.
