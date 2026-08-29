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
- Guest study state: browser localStorage key `n2-word-service:study-state:v1`
- Account study state: `data/users.sqlite` (or `N2_WORD_SERVICE_USERS_DB`)
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
- `item_marks` and `word_marks`: preserved legacy Known/Flagged evidence used
  only to seed guest study state during the transition. Startup migration
  `word_service_migrations/exclusive-mark-v1` normalizes dual rows with
  Flagged precedence. New learner state is never written here.

## Study-state database design

The content database and learner database now have separate responsibilities:

- `data/n2vocab.sqlite` is vocabulary content and immutable legacy migration
  evidence. It is not the account study-state source of truth.
- `data/users.sqlite` is the account study-state source of truth. The
  `study_cards` primary key is `(user_id, item_uuid)`, so the same vocabulary
  item can have different progress for different learners.
- Each `study_cards` row stores one `status`: `unmarked`, `known`, or `flagged`.
  The SQLite `CHECK` constraint makes the allowed values explicit; there are
  no account-level `known` and `flagged` booleans anymore.
- `enrolled_at`, `due_at`, `review_level`, playback provenance, and mark
  timestamps remain on the same card, but marking is not a review grade.

When old data contains both booleans, the migration rule is deterministic:
`flagged` wins over `known`; otherwise a lone `known` becomes `known`; neither
becomes `unmarked`. The same rule is used by the React localStorage migration,
guest import, account migration, and the legacy content seed.

For an explicit maintenance run, stop the service, make recoverable copies of
both SQLite files, then run from the project root:

```powershell
cargo run --manifest-path wordService/Cargo.toml --bin migrate_local_databases
```

The command is idempotent and uses the normal `N2_WORD_SERVICE_*` path
environment variables. It runs the content bridge migration and the account
`study_cards` migration without starting the HTTP server. Verify the database
invariants before restarting the service.

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
http://127.0.0.1:8767/           # React study wall (default)
http://127.0.0.1:8767/audio-review.html
```

### One-click Windows launcher

To build the compiled service and create the friendly project-root executable
`Start N2 Vocabulary.exe`, run this from PowerShell at the repository root:

```powershell
.\tools\build_start_n2_vocabulary.ps1
```

The launcher checks whether port `8767` is already serving WordService. If it
is not, it starts the release service, waits for `HEAD /api/summary` to return
HTTP 200, and opens the React study wall at `http://127.0.0.1:8767/`. The
service remains a separate process and is reused by later clicks.

Startup output from the service is appended to
`n2-word-service-launcher.log` beside the launcher. The build script uses
`wordService\target\launcher-release\release` so a currently running service
does not block a rebuild; the launcher also recognizes the normal
`wordService\target\release` layout and a `wordService` subdirectory for a
simple copied distribution. You can override the executable path with
`N2_WORD_SERVICE_EXECUTABLE` when packaging it elsewhere.

The Windows executable embeds the product icon from
`wordService\assets\n2-vocabulary.ico`. The favicon, ICO, and Android launcher
icons are generated from the approved
`wordService\assets\n2-vocabulary-tanuki-master.png` artwork. To regenerate
them after changing that source art, run:

```powershell
.\tools\build_start_n2_vocabulary.ps1 -RegenerateIcon
```

Optional environment variables:

- `N2_WORD_SERVICE_DB`
- `N2_WORD_SERVICE_USERS_DB` defaults to `data/users.sqlite`
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
- `POST /api/entries/<entry_id>/audio`
- `POST /api/entries/<entry_id>/examples/<position>/audio`
- `POST /api/units/<unit_number>/flagged-audio`
- `GET /audio/<clips/...>`

Study state and account endpoints:

- `GET /api/study/legacy-seed` returns unique shared item UUIDs and legacy
  marks for the one-time guest migration.
- `POST /api/auth/register`, `POST /api/auth/login`, and
  `POST /api/auth/logout` manage local email/password sessions.
- `GET /api/auth/me` returns the active user and CSRF token.
- `GET /api/study/state` returns the authenticated user's complete snapshot.
- `PUT /api/study/cards/<item_uuid>/marks` and
  `POST /api/study/cards/<item_uuid>/played` update one account card.
- `POST /api/study/cards/<item_uuid>/review-complete` atomically advances one
  due card when its supplied `expected_due_at` still matches the stored card.
- `POST /api/study/import-guest` conservatively merges an explicitly selected
  guest snapshot. Authenticated mutations require `X-CSRF-Token`.

## Review filter

The active React study wall exposes `Review` beside `All`, `Unmarked`, `Known`,
and `Flagged`.
Review shows cards whose playback-created `due_at` timestamp has arrived.
Playback completion—not a mark—enrolls a shared vocabulary item at level 0,
with its first review due after one day. A complete word-plus-available-sentence
playback inside Review advances its level and sets the next due date to
`2^level` days: 2, 4, 8, 16, 32, and so on. Replaying an enrolled card updates
its preferred book occurrence without changing its level or due time.

Entering Review captures the currently due cards for the selected book,
section, and search scope. A completed card stays visible as `Reviewed` for the
rest of that session; leave and re-enter Review to build a new due list. The
completion endpoint compares the original due timestamp inside its SQLite
transaction, so a second tab or a stale replay cannot advance a card twice.

Known and Flagged are mutually exclusive learner statuses. Selecting Flagged
clears Known; selecting Known clears Flagged; selecting the active status clears
the mark. If old data contains both, Flagged is always the effective status.
Marking never enrolls a card, changes its due time, or acts as a review grade.
The old graded-review route and Again/Hard/Good controls were removed so the
visible filter and the stored study state have one clear responsibility.

Guest JSON is validated and normalized when loaded. The exclusive-status upgrade
archives local version-2 state under `:pre-exclusive-mark:` before preserving
its schedule and playback provenance while converting legacy booleans to one
status. The level-scheduler upgrade archives local version-1 state under
`:pre-spaced-review:` before preserving only its tags and normal playback
provenance; old review dates and grades are discarded. Registered accounts
receive the exclusive-status migration through `exclusive-mark-v1`; the
existing `spaced-review-v1` marker remains responsible only for the earlier
scheduler reset. Malformed input is copied
to a timestamped `:malformed:` localStorage key before a fresh snapshot is
started, and the `storage` event updates other same-origin tabs. On first guest
launch, legacy Known and Flagged items retain only their tags; legacy marks do
not create review enrollment. The migration marker is
`n2-word-service:study-state:legacy-migrated:v1`.

After account login, guest progress is never uploaded silently. Import creates
one recoverable `n2-word-service:study-state:v1:import-archive:` copy before
upload, uses a client import ID and checksum for retry safety, and clears the
active guest snapshot only after the server transaction succeeds. **Keep
account progress** leaves guest state available for later logged-out use;
**Cancel** logs out and keeps guest mode active. Registered changes go only to
`users.sqlite`; localStorage is not an offline account write queue.

`users.sqlite` stores normalized emails, Argon2id password hashes, hashed
session tokens, CSRF tokens, card schedules, and import receipts. Raw session
tokens exist only in HttpOnly, SameSite=Lax cookies. The local HTTP cookie
intentionally omits `Secure`: do not expose this account service publicly
until it is behind HTTPS and Secure cookies. There is no email verification,
password recovery, OAuth, or administrator interface in this version.

To recover from a guest-import problem, inspect the one retained import archive
in the same browser profile before making further progress changes. To back up
registered progress, stop the service and copy `data/users.sqlite` (or the path
configured by `N2_WORD_SERVICE_USERS_DB`). Never copy a live SQLite database
without its active WAL/sidecar files.

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

Every audio URL returned by the API includes `?v=<full-sha256>`, calculated
from the MP3 bytes. Those exact versioned URLs are served with
`Cache-Control: public, max-age=31536000, immutable`; a file that changes gets
a different URL. Older unversioned `/audio/...` links remain usable for one
compatibility period: they receive a `307` redirect with `Cache-Control:
no-store` to the current versioned URL. A stale or forged version hash returns
`404` instead of serving new bytes under an old immutable cache key.

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

The player’s playback-mode button cycles through four transport runs. Its
icons are intentionally distinct: a speaker for one audio, a bulleted list
for one list, repeat arrows for a cycling list, and a queue for continuing to
the following section.

- `Single audio` plays only the currently focused recipe occurrence, then
  stops.
- `Play list once` follows every available occurrence in the listening
  sequence and every visible entry, then stops at the end of the current list.
- `Cycle this list` returns to the first playable entry when the current list
  ends and continues until the learner pauses it.
- `Continue to next list` moves to the following Section when the current
  Section ends. It stops after the final Section. With `All sections` selected,
  the visible entries are already one list, so it also stops at that list's end.

Open the gear button to edit the local `Listening sequence` recipe. Each row
has an audio element (`word` or `sentence`), a repeat count, and its own
pause-after duration. Add the same element more than once when a
learner wants a pattern such as word → sentence → sentence or word → sentence
→ word. A repeat count of zero skips a row, and an unavailable clip is skipped
automatically. The compatibility default remains one word followed by one
sentence, each with a 500 ms pause.

The recipe, transport mode, and pause values are saved in the browser’s local
playback settings. Existing v1 settings are migrated the first
time the React wall reads them; the runtime still uses only the browser’s
local learner state and the server’s SQLite/media projection.

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
cd frontend
corepack pnpm install --frozen-lockfile
pnpm check
```

The frontend is an independent pinned pnpm project. Always install and run its
commands from `wordService/frontend`; the repository root is not a JavaScript
workspace. The Rust tests build a temporary SQLite database and do not touch
the real vocabulary DB.

## Legacy Python

The previous Python backend and its tests live in `legacy/python/`. They are
kept only as a reference snapshot. The active frontend, API behavior, DB write
rules, and TTS queue contract should be read from the Rust code and Rust tests.
