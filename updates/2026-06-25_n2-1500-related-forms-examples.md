# N2_1500 Related Forms as Examples

## Result

- Moved `N2_1500` related-form markdown into normal `entry_examples` rows.
- Added optional `entry_examples.reading` support so bracket readings such as `[しょくぶつ]` are preserved separately from the related-form text.
- Kept the original related-form marker in `entry_examples.category`: `連`, `合`, `対`, `類`, or `慣`.
- Removed `### Related forms` blocks from `entries.explanation_md`; accent, part of speech, and source form remain as word-level explanation metadata.
- Updated `tools/import_n2_must_1500.py` so future imports write related forms directly to `entry_examples` instead of rebuilding the markdown block.

## Migration

```powershell
python tools\extract_related_forms.py --db wordService\data\n2vocab.sqlite --apply
```

The apply run created this SQLite backup:

- `wordService/data/n2vocab.sqlite.backup_before_related_forms_extract_20260625_203108`

Applied summary:

- Entries scanned: 1,591
- Entries with related forms: 861
- Related-form example rows inserted: 919
- Explanations stripped: 857
- Skipped lines: 0

Spot check:

- `N2_1500 #062 園芸` now has `entry_examples.position = 1`, `category = 合`, `text = 園芸植物`, `reading = しょくぶつ`, and `translation_zh = 园艺作物`.

## Validation

```powershell
python -m py_compile tools\extract_related_forms.py tools\import_n2_must_1500.py tools\test_import_n2_must_1500.py tools\test_import_green_word_book.py
python -m unittest tools.test_import_n2_must_1500 tools.test_import_green_word_book
cd wordService\rust
cargo fmt --check
cargo test
```

SQLite checks:

- `PRAGMA integrity_check`: `ok`
- `PRAGMA foreign_key_check`: 0 rows
- Remaining `N2_1500` `### Related forms` headings: 0
- Related-form `N2_1500` example rows: 919
- Related-form rows with preserved readings: 248
