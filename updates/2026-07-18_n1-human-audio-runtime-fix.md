# 2026-07-18 - N1 human-cut audio runtime fix

## Why

The imported N1 database records already referenced the reviewed human-cut word
and main-sentence clips, but the running release executable was older than the
per-book audio schema. For shared vocabulary identities such as `用心`, that
binary read the shared-item fallback and could expose generated or another
book's audio in the N1 view.

## What changed

- Kept the accepted N1 source audio and the correct SQLite rows unchanged.
- Added a repository regression test proving that a book-specific word and
  main-sentence clip overrides shared generated audio in both list and detail
  payloads.
- Rebuilt the optimized Rust service and restarted the local server on port
  `8767` with the current per-book lookup logic.
- Preserved the previous executable as
  `wordService/target/release/n2-word-service-rust.exe.backup_before_n1_human_audio_20260718`.

## Validation

- `cargo fmt --check` passed after formatting.
- `cargo test` passed 24 tests: 2 HTTP tests and 22 repository tests.
- SQLite contains 1,170 contiguous N1 entries; every `book_entries.word_clip`
  and `sentence_clip` uses the stable `clips/n1/` path for its source index.
- All 2,340 imported files match the accepted Mimikara N1 cut-audio source by
  file size and SHA-256; there were zero mismatches.
- `PRAGMA integrity_check` returned `ok` and `PRAGMA foreign_key_check` returned
  zero rows.
- Live API checks for shared identities including `葬式`, `世間`, `顔つき`,
  `用心`, `規制`, and `規模` now return N1 human word and main-sentence URLs.
  `用心` resolves to `Word0022.mp3` and `Sentence0022.mp3`.

## Residual notes

Before this runtime fix, 200 N1 shared identities could bypass their imported
book-specific word clip: 79 fell back to generated audio, 111 to another book's
human recording, and 10 had a blank shared clip. The current release uses the
N1 book-specific clip for all 1,170 entries.
