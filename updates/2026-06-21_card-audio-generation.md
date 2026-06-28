# 2026-06-21 - Card audio generation

## Why

The detail popup could generate a missing sentence MP3, but clicking a study
card only played audio that already existed. Imported cards without clips
needed one card-level action that prepares both pronunciation and sentence
audio.

## What changed

- Added `POST /api/entries/<entry_id>/audio` to reuse or generate word audio.
- Persisted generated word paths in `entries.word_clip` with the same atomic
  database-update pattern used for generated sentence audio.
- Made non-button card clicks ensure both word and main-sentence audio, then
  download both files into the browser cache.
- Kept star, known, flagged, cover, and details buttons independent of the
  card-level audio action.
- Documented both audio-generation endpoints in the service READMEs.

## Validation

- `cargo test --quiet`: 21 repository tests passed.
- `node --check wordService/static/app.js` passed.
- A throwaway database and clips directory generated both MP3s, persisted both
  paths, reused them on the second request, and served both audio files over
  HTTP. The live study database was not modified by this smoke test.

## Residual

The in-app browser runtime rejected its startup metadata during this run, so
the rendered click itself was not automated. The frontend handler was checked
for syntax and served from the running Rust application.
