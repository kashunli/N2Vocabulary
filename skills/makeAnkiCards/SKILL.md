---
name: make-anki-cards
description: Build, inspect, or repair the N2 Vocabulary Anki deck outputs using the current SQLite database and service-facing audio clips. Use when working on N2Words.apkg, N2Words_listening.apkg, card templates, media references, deck exports, or Anki validation for this repository.
---

# Make Anki Cards

This is the project-local Anki workflow for `D:\n2Prepare\N2Vocabulary`.
Keep it inside `skills/makeAnkiCards/`, because the deck builders depend on the
current project contract: `output/n2vocab.sqlite`, flat clip aliases under
`clips/`, and the same card identity used by prior N2 decks.

## Current Source Of Truth

- **Vocabulary and explanations**: `output/n2vocab.sqlite`
- **Word audio**: `clips/words/word<entry_id>.mp3`
- **Main sentence audio**: `clips/sentences/sentence<entry_id>.mp3`
- **Generated sentence audio**: `clips/generated_sentences/edge_tts/`
- **SQLite audio fields**: `entries.word_clip` and `entry_examples.audio_clip`
- **Example translations**: `entry_examples.translation_en` for the main
  sentence at `position = 0` and extra examples at `position > 0`
- **Deck outputs**: `output/N2Words.apkg` and `output/N2Words_listening.apkg`

The builders call `db.connect.load_entries()`, which reads SQLite with
`immutable=1` and returns the old list-of-dicts shape. This preserves the
existing templates and stable Anki note GUID formulas while using current DB
content.

## Scripts

- `scripts/make_anki.py` builds the word-centered deck.
  - Deck name: `耳から覚える::N2Words`.
  - The Anki template does not loop over database rows. The script pre-renders
    extra examples into five ordered fields: `MoreExample1` through
    `MoreExample5`. Extra example 6+ is intentionally omitted.
  - Japanese sentence fields are rendered through `scripts/anki_render.py`, so
    kanji-bearing tokens get `<ruby><rt>...</rt></ruby>` furigana.
- `scripts/make_anki_listening.py` builds the listening deck.
  - Deck name: `耳から覚える::N2WordsSentences`.
  - The back side shows the main sentence English translation and the same
    pre-rendered translated/explained extra examples in `MoreExample1` through
    `MoreExample5`.
  - It uses the same furigana renderer for the main sentence and extra example
    sentences.
- `scripts/make_clean_db.py` and `scripts/merge_explanations.py` are legacy
  helpers kept only for archaeology unless the user explicitly asks to repair
  old JSON-era data.

Do not add new Anki logic as loose root scripts. Keep deck code in this folder.

## Before Rebuilding

Run these commands from `D:\n2Prepare\N2Vocabulary` if audio clips may have
changed:

```powershell
python skills/cutTwice/flatten_audio_clips.py
python skills/cutTwice/flatten_audio_clips.py --apply --migrate-db
```

The dry run checks whether track-folder clips can be copied into flat service
aliases. The apply run copies aliases and updates SQLite audio columns only
after the sources are complete and unambiguous.

## Build Commands

Run from `D:\n2Prepare\N2Vocabulary`:

```powershell
python -u .\skills\makeAnkiCards\scripts\make_anki.py
python -u .\skills\makeAnkiCards\scripts\make_anki_listening.py
```

Optional explicit form:

```powershell
python -u .\skills\makeAnkiCards\scripts\make_anki.py --db output\n2vocab.sqlite --clips clips --out output\N2Words.apkg
python -u .\skills\makeAnkiCards\scripts\make_anki_listening.py --db output\n2vocab.sqlite --clips clips --out output\N2Words_listening.apkg
```

## Validation

- Confirm both builders print the expected note count.
- Confirm media counts and missing audio counts.
- Inspect the `.apkg` files as zip archives if media embedding is uncertain.
- Preserve stable deck IDs, model IDs, and `genanki.guid_for(...)` formulas
  unless the user explicitly wants a new deck identity.
- Treat SQLite and flat clip aliases as authoritative. Filename search is only
  fallback behavior for older data.

## Study-Ready Outputs

Use the deck files in `output/` directly:

- `output/N2Words.apkg`
- `output/N2Words_listening.apkg`
