# N2 wordService

`wordService` is the local card-study service for the N2 vocabulary repo.

The Rust implementation in this folder is the only active source of truth. The
old Python implementation has been moved to `legacy/python/` for archaeology
only. Do not use the legacy Python files for new behavior, bug fixes, or
workflow decisions unless the user explicitly asks to inspect history.

The code is intentionally split into a few small learning-oriented modules:

- `src/config.rs` reads runtime paths and environment variables.
- `src/audio_review.rs` owns the signed audio/text review queue and its
  separate SQLite decision store.
- `src/repository.rs` is the SQLite boundary and contains most business logic.
- `src/http.rs` is the tiny HTTP server and route table.
- `src/models.rs` contains JSON response structs.
- `src/tts.rs` owns the single-worker Microsoft Edge TTS queue.
- `tests/repository_tests.rs` exercises repository behavior with a temporary
  SQLite database.

## Inputs

- Vocabulary DB: `data/n2vocab.sqlite`
- Audio clips: `../clips/`; original N2 playback uses flat aliases while
  imported books can use explicit book-scoped paths such as `../clips/n1/`
- Frontend assets: `static/`
- Study marks: `item_marks` table in the same SQLite DB
- Generated sentence audio: `../clips/generated_sentences/edge_tts/`
- Review candidates: `../reviews/vocabulary_audio/n2_all_both_candidates.json`
- Seeded human decisions: `../reviews/vocabulary_audio/n2_all_both.json`
- Live review decisions: `data/audio_reviews.sqlite` (separate from the
  canonical vocabulary database)

## Vocabulary Data Flow

At runtime the service reads vocabulary directly from SQLite, not from a JSON
file. The default DB path is resolved in `src/config.rs` from this
`wordService/` folder as `data/n2vocab.sqlite`.

Important tables:

- `units`: unit headers and titles.
- `vocabulary_items`: one row per shared learnable item. `kanji` is the
  display headword, including kana-only words.
- `book_entries`: one row per book appearance. `source_index` is the
  word/book number used by book views; `unit_number` and `position` place it
  in the UI. `entry_id` remains the API compatibility placement ID. Meanings,
  verb pattern, word audio, main sentence, and sentence audio may override the
  shared-item compatibility values for that specific book.
- `item_examples`: sentence/example/term rows. `kind` names the role
  (`main_sentence`, `example_sentence`, `related_term`), while `position` is
  display order.
- `item_source_notes`: word-level meanings and notes preserved from a merged
  source book row.
- `item_example_sources`: provenance linking a normal example row back to its
  merged source record.
- `item_marks`: shared known/flagged state written by the study UI.

Exact GWB duplicates are merged into N2/N3 with a dry-run-first command:

```powershell
python tools/merge_gwb_duplicates.py
python tools/merge_gwb_duplicates.py --apply
```

The apply command creates a timestamped database backup, preserves GWB notes
and examples with provenance, removes only matched GWB rows, and runs SQLite
integrity checks. GWB and destination importers also reconcile this preserved
content so a rebuild does not silently discard it.

The Mimikara N1 book and its reviewed audio are imported from the sibling
digitization project with:

```powershell
python tools/import_mimikara_n1.py
```

The importer validates the complete 1,170-entry source, derives unit placement
from the accepted audio track manifest, copies 2,340 clips under `clips/n1/`,
and runs SQLite integrity and foreign-key checks. Source PDF/audio and source
review artifacts remain read-only.

When a displayed word is wrong, inspect `book_entries`, `vocabulary_items`, and
`item_examples` first.
For example, a browser issue like "word no.1025 in unit12 is wrong" should map
to `book_entries.unit_number = 12` and `book_entries.source_index = 1025`. See
`../docs/RUNBOOK.md` for copy-paste SQLite inspection and backup commands.

## Run

Run from the N2Vocabulary project root:

```powershell
cd wordService
cargo run
```

Then open:

```text
http://127.0.0.1:8767/
http://127.0.0.1:8767/audio-review.html
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
- `N2_WORD_SERVICE_REVIEW_DB`
- `N2_WORD_SERVICE_REVIEW_EVIDENCE`
- `N2_WORD_SERVICE_REVIEW_SEED`

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

Audio/text review endpoints:

- `GET /api/audio-review`
- `PUT /api/audio-review/<source_index>` with `decision` set to `replace`,
  `keep`, `custom`, or `audio_problem`, plus optional `replacement_text`
  and `note`
- `DELETE /api/audio-review/<source_index>` to return an item to pending

The service imports the validated JSON decisions only when a review database is
first initialized. Later browser edits are authoritative in
`audio_reviews.sqlite`; they never modify canonical vocabulary text or audio.
Use **Export decisions** before applying changes through the validator/repair
workflow.

The audio-generation endpoints queue Microsoft Edge TTS jobs so only one remote
TTS request runs at a time. They store generated MP3s under
`../clips/generated_sentences/edge_tts/` and write the relative paths back to
the selected `book_entries.word_clip` or `item_examples.audio_clip`. Clicking a card outside its
buttons ensures and downloads both the word and main-sentence files.

The flagged-audio export endpoint builds one MP3 for the selected unit's
flagged words. The listening order is word audio, 1 second of silence, main
sentence audio, 2 seconds of silence, then the next flagged word. Exports are
written under `../clips/exports/flagged_units/` and require `ffmpeg` on `PATH`.

## Autoplay review controls

The Study Wall player automatically advances through the current visible card
scope. Doing nothing moves to the next word; review actions are optional.
During playback, the wall keeps the previously played card on the left, the
current card enlarged in the center, and the next card on the right. Each card
transition advances the page by one smooth vertical step.

- `Space`: start, pause immediately, or resume, even when a button has focus
- `R`: immediately restart the current card from its word audio
- `Left Arrow` / `A`: previous card
- `Right Arrow` / `D`: next card
- `F`: toggle flagged without interrupting playback
- `Enter` / `K`: toggle known without interrupting playback
- `Escape`: stop immediately

Shortcuts are ignored while a form field has focus, so normal typing stays
intact. Outside text entry, study actions reserve `Space` and `Enter`; neither
key activates a focused button or link.

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
cd wordService
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
