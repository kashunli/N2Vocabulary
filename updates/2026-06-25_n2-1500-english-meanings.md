# N2_1500 English Meanings

## Result

- Added concise English word meanings to all 1,488 `N2_1500` headword records in `data/n2_must_1500_vocab.json`.
- Updated `wordService/data/n2vocab.sqlite` so `entries.meaning_en` is populated for all `book_code = 'N2_1500'` rows.
- Left `entry_examples` untouched; this workflow did not add English translations to example sentences or related-form notes.
- Added `tools/enrich_n2_1500_english_meanings.py`, a DeepSeek-backed batch workflow with reusable JSON batch outputs and source/DB backups.
- Updated `tools/import_n2_must_1500.py` so future imports preserve optional `meaning_en` values from the source JSON.

## Generated Artifacts

- Batch output and summaries: `output/n2_1500_english_meanings_2026-06-25/`
- Source JSON backup: `output/n2_1500_english_meanings_2026-06-25/n2_must_1500_vocab.json.backup_before_english_meanings_20260625_145123`
- SQLite backup: `output/n2_1500_english_meanings_2026-06-25/n2vocab.sqlite.backup_before_english_meanings_20260625_145123`

## Validation

```powershell
$env:PYTHONPYCACHEPREFIX='output\pycache_check'
python -m py_compile tools\enrich_n2_1500_english_meanings.py tools\import_n2_must_1500.py tools\test_import_n2_must_1500.py
python -m unittest tools.test_import_n2_must_1500
```

Additional SQLite/source checks:

- JSON `meaning_en` count: 1,488 / 1,488.
- SQLite `N2_1500` `meaning_en` count: 1,488 / 1,488.
- `PRAGMA integrity_check`: `ok`.
- `PRAGMA foreign_key_check`: 0 rows.
- `entry_examples.translation_en` populated for `N2_1500`: 0 rows.
