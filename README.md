# N2 Vocabulary Digitalization

This repository combines several JLPT vocabulary books, including the Mimikara
N1 and N2 books, into two main study products:

- a local SQLite-backed word-study service
- Anki decks for word study and sentence listening

The current project truth is:

- `skills/cutTwice/` is the current audio-cutting workflow.
- `skills/makeAnkiCards/` is the current Anki deck workflow.
- `skills/batch-japanese-sentence-explanations/` is the current batch sentence-explanation workflow.
- `skills/japanese-sentence-explanation-skill/` and `skills/japanese-sentence-explanation.skill` preserve the reusable single-sentence explanation skill for later review.
- `wordService/` is the current local study service.
- `legacy/` is a reference archive, not the default place to run code from.

## Folder Map

- `audio/` - original N2 source MP3 tracks; imported books keep their source
  media immutable in their source repositories.
- `json/` - OCR/page JSON used by vocabulary and exercise workflows.
- `parse/` - OCR parser docs and parser project files, now flattened into this root repo.
- `wordService/data/n2vocab.sqlite` - current canonical vocabulary data used by the word runtime and Anki builders.
- `vocabulary.json.db` - retired JSON vocabulary snapshot kept only for reference/history.
- `clips/` - current service-facing audio clips, including the original flat
  aliases and book-scoped folders such as `clips/n1/`.
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

## Local verification gate

The GitHub Actions verification gate is also available locally. After cloning
the repository, install the versioned Git hook once from PowerShell:

```powershell
.\tools\install-git-hooks.ps1
```

Before a commit, the hook checks the staged paths. Frontend changes run locked
dependency installation, tests, TypeScript type-checking, and the Vite build.
Rust changes run formatting, strict Clippy, and tests. If the frontend build
changes `wordService/static/react-rail`, the generated files must be reviewed
and staged before the commit can proceed.

The complete gate can be run explicitly at any time:

```powershell
.\tools\verify.ps1 -Scope All
```

Focused runs are available while developing:

```powershell
.\tools\verify.ps1 -Scope Frontend
.\tools\verify.ps1 -Scope Rust
```

The hook is a local guard, so it can technically be bypassed with
`git commit --no-verify`; GitHub Actions remains the required final check.

## Canonical Vocabulary Flow

The study service and Anki builders do not read a separate JSON vocabulary file
at runtime. The current word data is `wordService/data/n2vocab.sqlite`.

For a bad word shown in the browser, start from the SQLite row:

- `vocabulary_items` is the canonical shared learnable item.
- `book_entries.source_index` is the book/global word number shown as
  `wordNNN`.
- `book_entries.unit_number` and `book_entries.position` place the item in a
  unit/book view.
- `vocabulary_items.kanji` and `vocabulary_items.reading` identify the shared
  item. Book-specific meaning, verb-pattern, word-audio, sentence, and
  sentence-audio values in `book_entries` override shared compatibility values.
- `item_examples.kind` is the content role (`main_sentence`,
  `example_sentence`, or `related_term`); `position` is display order.
- `item_examples` is authoritative for sentence/example text and audio.
- `book_entries.word_clip`, `book_entries.sentence_clip`, and
  `item_examples.audio_clip` point into `clips/`; shared-item clip values remain
  compatibility fallbacks for older books.

The Mimikara N1 dataset is imported reproducibly with
`python tools/import_mimikara_n1.py`. It validates all 1,170 canonical source
entries and their 2,340 accepted word/sentence clips before updating SQLite.

Operational debugging steps live in `docs/RUNBOOK.md`; service-specific API and
configuration details live in `wordService/README.md`.
