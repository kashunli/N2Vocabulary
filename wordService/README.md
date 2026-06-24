# N2 wordService

`wordService` is the local card-study service for the N2 vocabulary repo.

The Rust implementation in `rust/` is now the only active source of truth. The
old Python implementation has been moved to `legacy/python/` for archaeology
only. Do not use the legacy Python files for new behavior, bug fixes, or
workflow decisions unless the user explicitly asks to inspect history.

## Inputs

- Vocabulary DB: `data/n2vocab.sqlite`
- Audio clips: `../clips/`; Rust playback expects flat aliases in
  `../clips/words/` and `../clips/sentences/`
- Frontend assets: `static/`
- Study marks: `word_marks` table in the same SQLite DB
- Generated sentence audio: `../clips/generated_sentences/edge_tts/`

## Vocabulary Data Flow

At runtime the service reads vocabulary directly from SQLite, not from a JSON
file. The default DB path is resolved in `rust/src/config.rs`: from
`wordService/rust`, it points to `../data/n2vocab.sqlite`, shown here as
`data/n2vocab.sqlite` relative to this `wordService/` folder.

Important tables:

- `units`: unit headers and titles.
- `entries`: one row per vocabulary item. `source_index` is the global
  word/book number used by audio filenames like `word1025.mp3`; `unit_number`
  and `position` place it in the UI. `kanji` is the display headword, including
  kana-only words.
- `entry_examples`: example sentences. `position = 0` is the main sentence
  shown on the card and should match `entries.sentence`; later positions are
  extra examples.
- `entry_source_notes`: word-level meanings and notes preserved from a merged
  source book row.
- `entry_example_sources`: provenance linking a normal example row back to its
  merged source record.
- `word_marks`: known/flagged state written by the study UI.

Exact GWB duplicates are merged into N2/N3 with a dry-run-first command:

```powershell
python tools/merge_gwb_duplicates.py
python tools/merge_gwb_duplicates.py --apply
```

The apply command creates a timestamped database backup, preserves GWB notes
and examples with provenance, removes only matched GWB rows, and runs SQLite
integrity checks. GWB and destination importers also reconcile this preserved
content so a rebuild does not silently discard it.

When a displayed word is wrong, inspect `entries` and `entry_examples` first.
For example, a browser issue like "word no.1025 in unit12 is wrong" should map
to `entries.unit_number = 12` and `entries.source_index = 1025`. See
`../docs/RUNBOOK.md` for copy-paste SQLite inspection and backup commands.

## Run

Run from the N2Vocabulary project root:

```powershell
cd wordService/rust
cargo run
```

Then open:

```text
http://127.0.0.1:8767/
```

Optional environment variables:

- `N2_WORD_SERVICE_DB`
- `N2_WORD_SERVICE_CLIPS`
- `N2_WORD_SERVICE_STATIC`
- `N2_WORD_SERVICE_HOST`
- `N2_WORD_SERVICE_PORT`
- `N2_WORD_SERVICE_BOOK`
- `N2_WORD_SERVICE_TTS_VOICE` defaults to `ja-JP-KeitaNeural`
- `N2_WORD_SERVICE_TTS_RATE` defaults to `-10%`
- `N2_WORD_SERVICE_TTS_DIR` defaults to `clips/generated_sentences/edge_tts`

## API

- `GET /api/summary`
- `GET /api/units`
- `GET /api/entries?unit=1&state=all|known|flagged|unmarked&search=...`
  (`unit` is optional; omit it to search/list all units)
- `GET /api/entries/<entry_id>`
- `GET /api/marks`
- `PUT /api/marks/<entry_id>` with `{"known": true|false, "flagged": true|false}`
- `POST /api/entries/<entry_id>/audio`
- `POST /api/entries/<entry_id>/examples/<position>/audio`
- `POST /api/units/<unit_number>/flagged-audio`
- `GET /audio/<clips/...>`

The audio-generation endpoints queue Microsoft Edge TTS jobs so only one remote
TTS request runs at a time. They store generated MP3s under
`../clips/generated_sentences/edge_tts/` and write the relative paths back to
`entries.word_clip` or `entry_examples.audio_clip`. Clicking a card outside its
buttons ensures and downloads both the word and main-sentence files.

The flagged-audio export endpoint builds one MP3 for the selected unit's
flagged words. The listening order is word audio, 1 second of silence, main
sentence audio, 2 seconds of silence, then the next flagged word. Exports are
written under `../clips/exports/flagged_units/` and require `ffmpeg` on `PATH`.

Canonical word and main-sentence audio paths are maintained with:

```powershell
cd ..
python skills/cutTwice/flatten_audio_clips.py
python skills/cutTwice/flatten_audio_clips.py --apply --migrate-db
```

The script keeps track folders as repair/audit artifacts, copies flat aliases
by entry ID, and rewrites SQLite audio columns only after source clips are
complete and unambiguous.

## Validate

```powershell
cd wordService/rust
cargo fmt --check
cargo test
```

The Rust tests build a temporary SQLite database and do not touch the real
vocabulary DB. The backend writes mutable SQLite state through a temporary copy
and copies it back after commit; this keeps writes reliable on this Windows
workspace when stale SQLite sidecar files exist.

## Legacy Python

The previous Python backend and its tests live in `legacy/python/`. They are
kept only as a reference snapshot. The active frontend, API behavior, DB write
rules, and TTS queue contract should be read from the Rust code and Rust tests.
