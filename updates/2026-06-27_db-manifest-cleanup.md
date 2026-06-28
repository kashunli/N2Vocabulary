# DB Manifest Cleanup

- Made `wordService/data/n2vocab.sqlite` the default active SQLite path in the
  shared Python DB helper and migration help text.
- Added migrations for sentence stars and `entry_examples.kind`, with backfill
  rules for `main_sentence`, `example_sentence`, and `related_term`.
- Updated importers, Rust/Python loaders, tests, and docs so `kind` carries the
  row role while `position` stays display order.
- Added `tools/validate_db_manifest.py` for read-only health, kind-count, and
  main-sentence compatibility checks.
