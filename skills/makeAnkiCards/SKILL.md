---
name: make-anki-cards
description: Build, inspect, or repair the N2 Vocabulary Anki deck outputs from the current vocabulary database and audio clips. Use when working on N2Words.apkg, N2Words_listening.apkg, card templates, media references, deck exports, or Anki validation for this repository.
---

# Make Anki Cards

This is the project-local Anki workflow folder. It exists so future Anki work has one obvious AI-facing entry point instead of scattered legacy scripts.

## Current Status

The current Anki scripts live here:

- `scripts/make_anki.py` - builds `output/N2Words.apkg`
- `scripts/make_anki_listening.py` - builds `output/N2Words_listening.apkg`
- `scripts/make_clean_db.py` - optional converter from old combined DB shape into `vocabulary.json`
- `scripts/merge_explanations.py` - optional explanation batch merge helper

Do not add new Anki logic as loose root scripts. Keep Anki deck code inside this folder.

## Folder Contract

- **Input vocabulary DB**: `../../vocabulary.json` from this folder, or `vocabulary.json` from repo root
- **Input audio clips**: `../../clips/` from this folder, or `clips/` from repo root
- **Durable outputs now**: `output/N2Words.apkg`, `output/N2Words_listening.apkg`
- **Target durable outputs later**: `dist/anki/N2Words.apkg`, `dist/anki/N2Words_listening.apkg`
- **Work/review outputs**: `work/anki/` after the target layout exists
- **Cache/scratch**: `cache/anki/` after the target layout exists

## Build Commands

Run from repo root:

```powershell
python -u .\skills\makeAnkiCards\scripts\make_anki.py
python -u .\skills\makeAnkiCards\scripts\make_anki_listening.py
```

Optional explicit form:

```powershell
python -u .\skills\makeAnkiCards\scripts\make_anki.py --vocab vocabulary.json --clips clips --out output/N2Words.apkg
python -u .\skills\makeAnkiCards\scripts\make_anki_listening.py --db vocabulary.json --clips clips --out output/N2Words_listening.apkg
```

## Validation

- Check note count printed by both builders.
- Check media count and missing audio counts.
- Preserve stable deck IDs, model IDs, and `genanki.guid_for(...)` formulas unless the user explicitly wants a new deck identity.
- Clip fields in `vocabulary.json` are authoritative. Filename search is only a fallback for old data.

## Current Rule

If asked to change Anki behavior, make the change in `skills/makeAnkiCards/scripts/` and keep `vocabulary.json` plus `clips/` as the default inputs.
