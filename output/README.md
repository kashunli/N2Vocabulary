# Output Folder Guide

`output/` is now a compatibility folder. It still exists because older scripts and artifacts used hardcoded paths, but new workflow design should follow the model in `docs/ARCHITECTURE.md`: final products in `dist/`, review/mapping artifacts in `work/`, and disposable ASR files in `cache/`.

## Current Contents

- `N2Words.apkg` - built word-centered Anki deck.
- `N2Words_listening.apkg` - built listening deck.
- `vocabulary_missing_restored.json` - repair/support data.
- `alignment/` - active and historical audio alignment work artifacts.
- `explanations/` - sentence explanation generation artifacts.
- `clips/` - older compatibility clip output. Current `cutTwice` output belongs in root `clips/`.
- `whisper_tmp/` - disposable Whisper scratch.

## Alignment Folder

- `alignment/review/` - per-track and per-unit review JSON.
- `alignment/entries/` - per-track expected entry lists.
- `alignment/mappings/` - mapping JSON produced by earlier workflows.
- `alignment/audits/` - clip audit reports and transcript caches.

These files are work evidence, not final products. Keep them when they explain a repair decision; prune or move caches when they only speed up reruns.

## Current Product Locations

- Canonical vocabulary DB: `vocabulary.json` at the project root.
- Current cut clips: `clips/` at the project root.
- HTML words/exercises: `wordsAndExerciseInHtml/`.
- Anki decks: currently `output/*.apkg`; target future location is `dist/anki/`.

## Cleanup Rule

Do not bulk-delete old audio clips or `*-deduced.mp3` files unless you have checked whether `vocabulary.json` or older DB snapshots still reference them.
