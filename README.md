# N2 Vocabulary Digitalization

This repository turns an OCR'd JLPT N2 vocabulary book plus its audio tracks into two main study products:

- a static HTML study site for vocabulary and exercises
- Anki decks for word study and sentence listening

The current project truth is:

- `cutTwice/` is the current audio-cutting workflow.
- `wordsAndExerciseInHtml/` is the current HTML build workflow.
- Anki building is still reference/legacy-backed and should be promoted into its own clean workflow before major new work.
- `legacy/` is a reference archive, not the default place to run code from.

## Folder Map

- `audio/` - source MP3 tracks from the book audio.
- `json/` - OCR/page JSON used by vocabulary and exercise workflows.
- `parse/` - OCR parser docs and parser project files, now flattened into this root repo.
- `vocabulary.json` - current canonical vocabulary data used by HTML and card workflows.
- `clips/` - current cut audio clips, arranged by logical unit/track folders.
- `cutTwice/` - current pair-first audio cutter and transcriber skill.
- `makeAnkiCards/` - project-local Anki skill entry point; implementation still needs promotion from `legacy/parse-scripts/`.
- `wordsAndExerciseInHtml/` - static HTML words and exercises.
- `output/` - current historical/working output bucket; see `docs/ARCHITECTURE.md` for the target split.
- `legacy/` - old scripts, old skills, backups, and preserved parser history.
- `updates/` - dated change records and cleanup notes.
- `docs/` - compact current architecture, runbook, and decisions.

## Maintenance Rule

Keep current workflows boring and explicit. Put reusable current code in named workflow folders, put historical material in `legacy/`, and put narrative history in `updates/`. Avoid adding one-off scripts at the repository root.

This repo is AI-operated first: prefer small concrete skill folders with `SKILL.md` plus nearby scripts, because future work will usually be performed by an AI agent reading the repo rather than by a human remembering command history.
