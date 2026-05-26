# N2 wordService Rust

This folder contains the authoritative backend for `wordService`. It serves the
static frontend from `../static`, reads the vocabulary SQLite database, resolves
audio from the project `clips/` tree, and owns lazy sentence-audio generation.
Normal word and main-sentence playback should use flat DB paths:
`clips/words/wordNNN.mp3` and `clips/sentences/sentenceNNN.mp3`.

The code is intentionally split into a few small learning-oriented modules:

- `src/config.rs` reads runtime paths and environment variables.
- `src/repository.rs` is the SQLite boundary and contains most business logic.
- `src/http.rs` is the tiny HTTP server and route table.
- `src/models.rs` contains JSON response structs.
- `src/tts.rs` owns the single-worker Microsoft Edge TTS queue.
- `tests/repository_tests.rs` exercises repository behavior with a temporary
  SQLite database.

## Run

From this folder:

```powershell
cargo run
```

Then open:

```text
http://127.0.0.1:8767/
```

To use a different port:

```powershell
$env:N2_WORD_SERVICE_PORT = "8768"
cargo run
```

## Validate

```powershell
cargo fmt --check
cargo test
```

The tests create a temporary SQLite DB and do not touch the real study DB.

## Canonical Audio Paths

Track folders under `clips/unit*_track*/` remain useful repair evidence because
they preserve source-track manifests. The service-facing paths are flat aliases
maintained from the project root:

```powershell
python skills/cutTwice/flatten_audio_clips.py
python skills/cutTwice/flatten_audio_clips.py --apply --migrate-db
```

The read-only audit reports missing, duplicate, stale, and noncanonical paths.
Apply mode copies real files into `clips/words/` and `clips/sentences/`; DB
migration updates `entries.word_clip`, `entries.sentence_clip`, and position-0
`entry_examples.audio_clip`.

## Clean Sentence Text

Edge TTS should receive a plain sentence, not textbook shorthand. The backend
cleans clicked sentence text before synthesis, and the same rule can be applied
to SQLite rows when OCR/imported examples contain notation like `｛な／の｝`,
furigana parentheses, leading sense numbers, or slash lists:

```powershell
cargo run --bin clean_sentence_text -- --preview-limit 20
cargo run --bin clean_sentence_text -- --apply
```

Preview mode prints changes only. Apply mode creates a timestamped SQLite
backup, updates `entry_examples.text`, deletes marker-only rows, reindexes
example positions per entry, syncs `entries.sentence` from position `0`, and
clears generated Edge-TTS links for changed rows so audio can be regenerated
from the cleaned sentence.

## Lazy Sentence Audio

The detail popup can generate missing example-sentence audio. The frontend
calls:

```text
POST /api/entries/<entry_id>/examples/<position>/audio
```

The backend queues jobs through one TTS worker thread, so Microsoft Edge TTS is
called serially even if the user clicks several missing sentences quickly. MP3s
are saved under `clips/generated_sentences/edge_tts/` by default, named like
`word101_sentence2.mp3`, then the relative path is stored in
`entry_examples.audio_clip`.

Optional environment variables:

- `N2_WORD_SERVICE_TTS_VOICE`
- `N2_WORD_SERVICE_TTS_RATE`
- `N2_WORD_SERVICE_TTS_DIR`

## Legacy Code

The old Python backend is archived in `../legacy/python/`. It is not the source
of truth for current behavior.
