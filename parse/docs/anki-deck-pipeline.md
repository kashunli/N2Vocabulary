# Anki Deck Pipeline Notes

This document describes the Anki export pipeline built from the generated vocabulary dataset and audio clips.

Implementation files:

- [`../scripts/build_anki_deck.py`](../scripts/build_anki_deck.py)

Outputs:

- [`output/anki/notes.json`](/mnt/d/n2Prepare/materialToLearn/N2Vocabulary/output/anki/notes.json)
- [`output/anki/notes.tsv`](/mnt/d/n2Prepare/materialToLearn/N2Vocabulary/output/anki/notes.tsv)
- [`output/anki/n2_vocabulary.apkg`](/mnt/d/n2Prepare/materialToLearn/N2Vocabulary/output/anki/n2_vocabulary.apkg)

## Goal

Generate a real Anki deck package from the combined vocabulary dataset while preserving:

- all 1098 entries
- available word and sentence audio
- review status for uncertain alignments
- a flat debug export that is easy to inspect outside Anki

## Data Source

The deck builder consumes:

- [`output/vocabulary_combined.json`](/mnt/d/n2Prepare/materialToLearn/N2Vocabulary/output/vocabulary_combined.json)

That file already includes:

- headword and reading
- meanings in English, Chinese, and Korean
- example sentences
- audio clip paths
- audio quality/review metadata

This means the deck builder does not need to re-run OCR parsing or audio alignment.

## Card Design

The implementation creates one note type with two templates:

### 1. Sentence to Word

Front:

- sentence 1
- sentence audio if available

Back:

- target word
- reading
- kanji
- term audio if available
- meanings in EN/ZH/KO
- all sentences
- audio status and review reasons

### 2. Word to Details

Front:

- target word
- reading
- word audio if available

Back:

- kanji
- verb pattern
- meanings in EN/ZH/KO
- sentence 1
- sentence audio if available
- all sentences
- audio status and review reasons

## Inclusion Rules

All entries are included.

Audio handling:

- if both clips exist and the item is not flagged, tag as `audio::clean`
- if clips exist but the alignment needs review, tag as `audio::review`
- if one or both clips are missing, tag as `audio::missing`

Other tags:

- `unit::XX`
- `has_kanji` or `no_kanji`
- `needs_review` when applicable

## Stable Identity

The builder uses:

- stable deck ID
- stable model ID
- stable per-note GUID derived from the global vocabulary index

This is important because rerunning the build should update notes in Anki rather than duplicating them.

## Export Formats

### `notes.json`

Primary normalized debug export.

Useful for:

- spot checking fields
- debugging card rendering
- future migrations or alternative exporters

### `notes.tsv`

Human-readable and spreadsheet-friendly export.

Useful for:

- quick filtering
- bulk inspection
- manual import experiments

### `.apkg`

The real Anki package, including referenced MP3 media files.

## Dependency Choice

The implementation uses `genanki` to write the `.apkg`.

Reason:

- it produces a real Anki package instead of only a text import
- it supports card templates, media packaging, and stable note GUIDs

## Running the Builder

```bash
python3 parse/scripts/build_anki_deck.py
```

## Notes About Media Packaging

The package includes only clips that actually exist on disk.

Audio fields reference media by basename:

- `word123.mp3`
- `sentence123.mp3`

This is safe because the filenames are globally unique by vocabulary index.

## Expected Behavior

After a successful run:

- every vocabulary entry becomes one note
- each note generates two cards
- the package includes all available clip media
- missing or review-flagged audio stays visible through fields and tags

## Future Improvements

Potential next steps:

1. add richer styling or furigana support
2. split the package into “clean audio” and “review” decks if needed later
3. add extra templates such as meaning-to-word recall
4. attach the original source track name as a hidden field for debugging
