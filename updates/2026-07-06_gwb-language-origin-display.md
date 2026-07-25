# 2026-07-06 - GWB language-origin display cleanup

## Why

Some GreenWordBook loanword rows imported a source-language origin note as the
display headword. For example, `法 jupon` appeared as the main word while the
Japanese learner-facing word `ズボン` was stored in the reading field.

## What Changed

- Updated `tools/import_green_word_book.py` so bracket notes that start with a
  source-language marker, such as `法 jupon` or `荷 koffie`, keep the Japanese
  headword in `kanji` and store the origin note in `reading`.
- Added importer tests covering both normal `bracket_form` input and misplaced
  bracketed origin notes in `reading`.
- Updated 33 live `GWB_N2` rows in `wordService/data/n2vocab.sqlite`, including
  the newer `vocabulary_items` layer, so web/API/Anki export paths see the same
  display values.

## Backup

Before the SQLite edit, a full backup was created:

`wordService/data/n2vocab.sqlite.backup_before_gwb_language_origin_display_20260706_182254`

## Verification

Commands run:

```powershell
python -m unittest tools.test_import_green_word_book
```

SQLite checks after the transaction:

- `PRAGMA integrity_check` returned `ok`.
- `PRAGMA foreign_key_check` returned `0` rows.

Spot checks:

- `GWB_N2 #4405`: `kanji = ズボン`, `reading = 法 jupon`.
- `GWB_N2 #705`: `kanji = コンクール`, `reading = 法 concours`.
- `GWB_N2 #49`: `kanji = コーヒー`, `reading = 荷 koffie`.

## Residual

Plain etymology-only bracket forms without a language marker, such as
`アイスクリーム【ice cream】`, were intentionally left unchanged. Converting all
plain loanword etymologies would be a broader presentation pass.
