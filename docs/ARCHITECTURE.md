# Architecture

## Artifact Levels

Use artifact level as the organizing principle:

- **Source**: human/source material that is expensive or impossible to regenerate, such as `audio/`, `json/`, and the PDF/OCR inputs under `parse/`.
- **Canonical data**: cleaned project state that downstream products read, especially `vocabulary.json`.
- **Work artifacts**: review files, mappings, audits, and repair manifests that explain how a result was produced.
- **Cache**: Whisper transcripts, temporary ASR folders, and other speed aids that can be regenerated.
- **Distribution**: final user-facing artifacts, such as HTML pages and `.apkg` decks.
- **Legacy**: old approaches preserved for reference only.

## Current Layout

The project still has a historical `output/` folder. Treat it as a compatibility bucket while cleanup continues:

- `output/alignment/` - work artifacts for mapping, review, and audit.
- `output/explanations/` - explanation generation artifacts.
- `output/*.apkg` - built Anki decks.
- `output/whisper_tmp/` - disposable scratch/cache.

The newer current workflows already live outside `output/`:

- `clips/` - current cut clips from `cutTwice/`.
- `wordsAndExerciseInHtml/` - current HTML site.
- `vocabulary.json` - current canonical vocabulary DB.

## Target Layout

When hardcoded legacy paths are retired, use this shape:

```text
N2Vocabulary/
├── audio/                  # source audio
├── json/                   # source OCR JSON
├── parse/                  # parser docs/source project
├── data/                   # canonical and normalized JSON
├── clips/                  # current cut audio clips
├── work/                   # mappings, audits, reviews, repair manifests
├── cache/                  # Whisper/temporary/regenerable files
├── dist/                   # final HTML exports and Anki decks
├── cutTwice/               # audio cutting skill and scripts
├── wordsAndExerciseInHtml/ # HTML build workflow
└── legacy/                 # old methods and archived history
```

## Skill Input/Output Contract

A good project-local skill should not own the whole repository layout. It should own a small contract:

- `--input` or `--track`: source file or source folder.
- `--output-dir`: durable output the user expects to keep.
- `--work-dir`: optional review/manifests if they should not live beside the output.
- `--cache-dir`: optional disposable cache/scratch.

For this repository, the default convention is:

- inputs from `audio/`
- durable audio clips to `clips/<logical-unit-track>/`
- pair manifests beside the clips as `clips/<logical-unit-track>/pairs.json`
- broader audit/review artifacts to `work/` or, during compatibility cleanup, `output/alignment/`
- temporary Whisper scratch/cache to `cache/` or ignored `output/whisper_tmp/`

Avoid designing a skill that silently writes into many folders. If a workflow needs multiple products, name them in the command or document each path in `SKILL.md`.

## AI-First Skill Folders

This project should be easier for AI agents than for a human clicking commands manually. Prefer this workflow shape:

```text
workflowName/
├── SKILL.md          # short agent-facing contract and procedure
├── scripts/          # deterministic helpers for this workflow
├── references/       # optional detailed schema/prompt notes
└── assets/           # optional templates or static resources
```

Keep each skill concrete. `cutTwice/` should only cut/transcribe audio clips. `makeAnkiCards/` should only build/check/export Anki decks. HTML generation belongs in `wordsAndExerciseInHtml/`.

When a skill grows too large, split it by product or decision surface. For example, audio cutting, clip audit, Anki building, and HTML rendering should be separate skills because they have different inputs, outputs, and validation checks.
