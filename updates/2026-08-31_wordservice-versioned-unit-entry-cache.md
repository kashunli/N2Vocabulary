# WordService versioned unit entry cache

## Why

Selecting any section caused the React client to call `/api/entries?book=...`
without a `unit`, so a cold local cache queried and serialized the entire book.
The cache was also stored as one large localStorage value.

## Contract

- `/api/summary?book=<book>` supplies the database `content_revision`.
- A selected section requests
  `/api/entries?book=<book>&unit=<unit>&v=<content_revision>`.
- The local cache key contains the same `(book, revision, unit)` tuple.
- A changed content revision therefore produces both a new request URL and a
  new local cache key; an old versioned URL returns 404.
- `All sections` is assembled from per-unit values. Cached units are reused and
  only missing units are requested, with at most four requests in flight.
- Unversioned entry URLs remain compatible and retain `Cache-Control: no-store`.

## Files

- Backend: `wordService/src/http/read.rs`, `http/response.rs`, `repository.rs`
- Frontend: `wordService/frontend/src/api.ts` and
  `features/study/{contentCache,useStudyCatalog,useStudyEntries}.mjs/.ts`
- Generated frontend: `wordService/static/react-rail`

## Validation

- `pnpm check`
- `cargo fmt --check`
- `cargo test`
- `cargo clippy --all-targets --all-features -- -D warnings`
