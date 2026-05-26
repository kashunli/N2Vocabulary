# N2 wordService

`wordService` is the local card-study service for the N2 vocabulary repo.

The Rust implementation in `rust/` is now the only active source of truth. The
old Python implementation has been moved to `legacy/python/` for archaeology
only. Do not use the legacy Python files for new behavior, bug fixes, or
workflow decisions unless the user explicitly asks to inspect history.

## Inputs

- Vocabulary DB: `../output/n2vocab.sqlite`
- Audio clips: `../clips/`; Rust playback expects flat aliases in
  `../clips/words/` and `../clips/sentences/`
- Frontend assets: `static/`
- Study marks: `word_marks` table in the same SQLite DB
- Generated sentence audio: `../clips/generated_sentences/edge_tts/`

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
- `N2_WORD_SERVICE_TTS_VOICE` defaults to `ja-JP-NanamiNeural`
- `N2_WORD_SERVICE_TTS_RATE` defaults to `-10%`
- `N2_WORD_SERVICE_TTS_DIR` defaults to `clips/generated_sentences/edge_tts`

## API

- `GET /api/summary`
- `GET /api/units`
- `GET /api/entries?unit=1&state=all|known|flagged|unmarked&search=...`
- `GET /api/entries/<entry_id>`
- `GET /api/marks`
- `PUT /api/marks/<entry_id>` with `{"known": true|false, "flagged": true|false}`
- `POST /api/entries/<entry_id>/examples/<position>/audio`
- `GET /audio/<clips/...>`

The audio-generation endpoint queues Microsoft Edge TTS jobs so only one remote
TTS request runs at a time. It stores generated MP3s under
`../clips/generated_sentences/edge_tts/` and writes the relative path back to
`entry_examples.audio_clip`.

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
