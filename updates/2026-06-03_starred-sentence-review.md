# 2026-06-03 - Starred Sentence Review

## Why

The study UI needed sentence-level starring, separate from word-level known/flagged marks. The approved design direction was a dedicated starred-sentence review page that defaults across all units, lists only starred sentences, links each sentence back to its source word, and shows a sentence-focused detail panel with explanation support.

## What Changed

- Added a Rust-owned `sentence_stars` SQLite table keyed by `(entry_id, position)`.
- Added repository methods to star/unstar individual `entry_examples` rows and list starred sentences globally or by unit.
- Added `GET /api/starred-sentences` with optional `?unit=<number>`.
- Added `PUT /api/entries/<entry_id>/examples/<position>/star` with `{"starred": true|false}`.
- Added `starred` state to example payloads and `sentence_starred` to list/detail entry payloads so the frontend can render star buttons accurately.
- Added a real starred-sentence review view to `static/index.html`, `static/app.js`, and `static/styles.css`.
- Added main-sentence star buttons on cards and per-example star buttons in the word detail popup.
- The starred review view defaults to all units, supports unit filtering, lists only starred sentences, shows source-word links, opens the original word detail, and renders sentence explanations when present.

## Validation

- `node --check static/app.js`
- `cargo fmt --check`
- `cargo test`
- Live API smoke test:
  - Starred a main sentence through the new PUT endpoint.
  - Confirmed it appeared in `GET /api/starred-sentences`.
  - Restored the sentence to its original starred state.
- Live UI screenshot captured at `wordService/tmp-preview/starred-sentences-live-review.png`.

## Residual Notes

- Some sentences do not have `entry_examples.explanation_md` yet. The UI intentionally shows a ready placeholder for the future sentence-explanation generation workflow.
- The old standalone prototype page was removed after the approved design was implemented in the active runtime page.
