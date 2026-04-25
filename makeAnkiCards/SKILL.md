---
name: make-anki-cards
description: Build, inspect, or repair the N2 Vocabulary Anki deck outputs from the current vocabulary database and audio clips. Use when working on N2Words.apkg, N2Words_listening.apkg, card templates, media references, deck exports, or Anki validation for this repository.
---

# Make Anki Cards

This is the project-local Anki workflow folder. It exists so future Anki work has one obvious AI-facing entry point instead of scattered legacy scripts.

## Current Status

This workflow is not fully promoted yet. The older working implementation lives in `legacy/parse-scripts/`, especially:

- `make_anki.py`
- `make_anki_listening.py`
- `make_clean_db.py`
- `merge_explanations.py`

Use those files as reference material when promoting code into this folder. Do not add new Anki logic as loose root scripts.

## Folder Contract

- **Input vocabulary DB**: `vocabulary.json`
- **Input audio clips**: `clips/`
- **Durable outputs now**: `output/N2Words.apkg`, `output/N2Words_listening.apkg`
- **Target durable outputs later**: `dist/anki/N2Words.apkg`, `dist/anki/N2Words_listening.apkg`
- **Work/review outputs**: `work/anki/` after the target layout exists
- **Cache/scratch**: `cache/anki/` after the target layout exists

## Promotion Plan

1. Copy only the still-needed Anki builder logic from `legacy/parse-scripts/`.
2. Put deterministic helpers under `makeAnkiCards/scripts/`.
3. Keep this `SKILL.md` short: commands, inputs, outputs, validation, and traps only.
4. Validate decks by checking note count, media references, model fields, and a small exported preview JSON.
5. Preserve card GUID/model behavior when updating existing decks so study progress survives.

## Current Rule

If asked to change Anki behavior before promotion is complete, first inspect the legacy scripts, then either make a narrow legacy-compatible fix or promote the needed script into `makeAnkiCards/scripts/` as part of the change.
