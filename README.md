# N2 Vocabulary Digitalization

This repository turns an OCR'd JLPT N2 vocabulary book plus its audio tracks into two main study products:

- a local SQLite-backed word-study service
- Anki decks for word study and sentence listening

The current project truth is:

- `skills/cutTwice/` is the current audio-cutting workflow.
- `skills/makeAnkiCards/` is the current Anki deck workflow.
- `skills/batch-japanese-sentence-explanations/` is the current batch sentence-explanation workflow.
- `skills/japanese-sentence-explanation-skill/` and `skills/japanese-sentence-explanation.skill` preserve the reusable single-sentence explanation skill for later review.
- `wordService/rust/` is the current local study service.
- `legacy/` is a reference archive, not the default place to run code from.

## Folder Map

- `audio/` - source MP3 tracks from the book audio.
- `json/` - OCR/page JSON used by vocabulary and exercise workflows.
- `parse/` - OCR parser docs and parser project files, now flattened into this root repo.
- `wordService/data/n2vocab.sqlite` - current canonical vocabulary data used by the word runtime and Anki builders.
- `vocabulary.json.db` - retired JSON vocabulary snapshot kept only for reference/history.
- `clips/` - current service-facing audio clips, especially `clips/words/` and `clips/sentences/`.
- `skills/` - reusable project-local skills and workflow folders for later review.
- `wordService/` - Rust word-study service and archived legacy Python service.
- `output/` - current historical/working output bucket; see `docs/ARCHITECTURE.md` for the target split.
- `legacy/` - old scripts, old skills, backups, and preserved parser history.
- `updates/` - dated change records and cleanup notes.
- `docs/` - compact current architecture, runbook, and decisions.
- `AGENTS.md` - project memory and AI-maintainable coding principles for future agents.

## Maintenance Rule

Keep current workflows boring and explicit. Put reusable current code in `skills/<name>/`, put historical material in `legacy/`, and put narrative history in `updates/`. Avoid adding one-off scripts at the repository root.

This repo is AI-operated first: prefer small concrete skill folders with `SKILL.md` plus nearby scripts, because future work will usually be performed by an AI agent reading the repo rather than by a human remembering command history.

## Canonical Vocabulary Flow

The study service and Anki builders do not read a separate JSON vocabulary file
at runtime. The current word data is `wordService/data/n2vocab.sqlite`.

For a bad word shown in the browser, start from the SQLite row:

- `entries.source_index` is the book/global word number shown as `wordNNN`.
- `entries.unit_number` and `entries.position` place the word in a unit.
- `entries.kanji`, `entries.reading`, `entries.headword_text`, meanings,
  `entries.sentence`, and `entries.explanation_md` feed the main card.
- `entry_examples` stores the main sentence at `position = 0` and extra example
  rows at later positions.
- `entries.word_clip`, `entries.sentence_clip`, and `entry_examples.audio_clip`
  point into `clips/`.

Operational debugging steps live in `docs/RUNBOOK.md`; service-specific API and
configuration details live in `wordService/README.md` and
`wordService/rust/README.md`.
