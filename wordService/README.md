# N2 wordService

`wordService` is the v1 local card-study service for the N2 vocabulary repo.
It keeps the frontend and backend separate while staying dependency-free.

## Inputs

- Vocabulary DB: `../output/n2vocab.sqlite`
- Audio clips: `../clips/`
- Study marks: `word_marks` table in the same SQLite DB

## Run

Run from the project root:

```powershell
python wordService/run_word_service.py
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

## API

- `GET /api/summary`
- `GET /api/units`
- `GET /api/entries?unit=1&state=all|known|flagged|unmarked&search=...`
- `GET /api/entries/<entry_id>`
- `GET /api/marks`
- `PUT /api/marks/<entry_id>` with `{"known": true|false, "flagged": true|false}`
- `GET /audio/<clips/...>`

## Validate

```powershell
python -m unittest discover -s wordService/tests -q
```

The tests build a temporary SQLite database and do not touch the real vocabulary
DB. The service itself uses the same copy-mutate-copy-back mark write behavior
as `marks_server.py`, because direct writes on this Windows-mounted workspace
can be fragile when stale SQLite WAL sidecars exist.

## Rust side-by-side version

The Rust backend lives in `wordService/rust/`. It mirrors the Python service API
while keeping the code split into small learning-oriented modules.

```powershell
cd wordService/rust
cargo run
cargo test
```

It uses the same `N2_WORD_SERVICE_*` environment variables as the Python
service. If the Python server is already running on `8767`, set
`N2_WORD_SERVICE_PORT=8768` before `cargo run`.
