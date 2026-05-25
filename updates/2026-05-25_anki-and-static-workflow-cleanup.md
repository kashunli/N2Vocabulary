# 2026-05-25 - Anki Builders And Static Workflow Cleanup

## Why

The active N2 vocabulary workflow has moved to SQLite-backed data, flat
service-facing audio aliases, the Rust `wordService`, and Anki package outputs
under `output/`. Several older folders and docs still pointed agents toward
JSON-era static HTML workflows or copy-only export folders.

## Decisions

- Keep `skills/makeAnkiCards/` as the active Anki skill location.
- Treat `output/n2vocab.sqlite` as the Anki data source.
- Treat `clips/words/`, `clips/sentences/`, and generated sentence clips as the
  active audio sources for decks and the service.
- Use `output/N2Words.apkg` and `output/N2Words_listening.apkg` directly as the
  study-ready deck outputs.
- Retire `D:\n2Prepare\ankiCardsToBuilt` as an old copy/export workspace.
- Retire `wordsAndExerciseInHtml/` and the old root `marks_server.py`; the
  current local study service is `wordService/rust`.

## What Changed

- Updated `skills/makeAnkiCards/scripts/make_anki.py` to read SQLite through
  `db.connect.load_entries()` instead of `vocabulary.json`.
- Updated `skills/makeAnkiCards/scripts/make_anki_listening.py` to use the same
  SQLite-backed source.
- Added English translations to both Anki deck templates:
  - main sentence translation
  - up to four extra examples with English translations
  - maximum visible sentence items per note: one main sentence plus four extras
- Preserved stable Anki deck IDs, model IDs, and note GUID formulas so importing
  rebuilt decks should update existing notes instead of resetting study
  progress.
- Updated docs to make `wordService/rust` the current study runtime and to stop
  pointing future agents at `wordsAndExerciseInHtml/` or `ankiCardsToBuilt/`.
- Deleted obsolete local-only `clips/unit*_track*` folders after confirming the
  DB no longer references them.
- Deleted the obsolete tracked `wordsAndExerciseInHtml/` tree and root
  `marks_server.py`.

## Validation

- `N2Words.apkg` rebuild:
  - `1160` notes
  - `2320` media files
  - `0` missing word audio
  - `0` missing sentence audio
- `N2Words_listening.apkg` rebuild:
  - `1160` notes
  - `2320` media files
  - `0` missing sentence audio
- Packaged deck inspection confirmed the new `SentenceTranslationEN` field and
  translated extra-example HTML are present.
- After deleting `clips/unit*_track*`, SQLite audio-path validation found `0`
  missing paths.
- `cargo test` in `wordService/rust` passed with `13` repository/service tests.

## Commits

- `00bb6ca Update N2 Anki deck builders`
- `ec80960 Remove obsolete static HTML workflow`

## Follow-Up Rule

For future minor or major updates whose context is too long for a commit
message, add a dated markdown record in `updates/` before or with the commit.
