# N2 Vocabulary Digitalization

This repository turns an OCR'd JLPT N2 vocabulary book plus its audio tracks into two main study products:

- a static HTML study site for vocabulary and exercises
- Anki decks for word study and sentence listening

The current project truth is:

- `skills/cutTwice/` is the current audio-cutting workflow.
- `skills/makeAnkiCards/` is the current Anki deck workflow.
- `skills/batch-japanese-sentence-explanations/` is the current batch sentence-explanation workflow.
- `skills/japanese-sentence-explanation-skill/` and `skills/japanese-sentence-explanation.skill` preserve the reusable single-sentence explanation skill for later review.
- `wordsAndExerciseInHtml/` is the current HTML build workflow.
- `legacy/` is a reference archive, not the default place to run code from.

## Folder Map

- `audio/` - source MP3 tracks from the book audio.
- `json/` - OCR/page JSON used by vocabulary and exercise workflows.
- `parse/` - OCR parser docs and parser project files, now flattened into this root repo.
- `output/n2vocab.sqlite` - current canonical vocabulary data used by the word runtime and HTML snapshots.
- `vocabulary.json.db` - retired JSON vocabulary snapshot kept only for reference/history.
- `clips/` - current cut audio clips, arranged by logical unit/track folders.
- `skills/` - reusable project-local skills and workflow folders for later review.
- `wordsAndExerciseInHtml/` - static HTML words and exercises.
- `output/` - current historical/working output bucket; see `docs/ARCHITECTURE.md` for the target split.
- `legacy/` - old scripts, old skills, backups, and preserved parser history.
- `updates/` - dated change records and cleanup notes.
- `docs/` - compact current architecture, runbook, and decisions.
- `AGENTS.md` - project memory and AI-maintainable coding principles for future agents.

## Maintenance Rule

Keep current workflows boring and explicit. Put reusable current code in `skills/<name>/`, put historical material in `legacy/`, and put narrative history in `updates/`. Avoid adding one-off scripts at the repository root.

This repo is AI-operated first: prefer small concrete skill folders with `SKILL.md` plus nearby scripts, because future work will usually be performed by an AI agent reading the repo rather than by a human remembering command history.
