# Architecture

## Artifact Levels

Use artifact level as the organizing principle:

- **Source**: human/source material that is expensive or impossible to regenerate, such as `audio/`, `json/`, and the PDF/OCR inputs under `parse/`.
- **Canonical data**: cleaned project state that downstream products read, especially `wordService/data/n2vocab.sqlite`.
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

- `clips/` - current service-facing clips from `skills/cutTwice/`, flattened under `clips/words/` and `clips/sentences/`.
- `wordService/rust/` - current local SQLite-backed study service.
- `skills/` - reusable project-local skill/workflow folders.
- `wordService/data/n2vocab.sqlite` - current canonical vocabulary DB.
- `vocabulary.json.db` - retired JSON snapshot kept for reference only.

## Vocabulary Data Flow

`wordService/data/n2vocab.sqlite` is the canonical vocabulary data store for current
runtime and deck workflows. The local service, Anki builders, and most repair
scripts read the same SQLite rows instead of independent vocabulary JSON.

```text
wordService/data/n2vocab.sqlite
  books, units
  entries              # one row per vocabulary item
    source_index       # global book/word number, e.g. word1025
    unit_number        # unit shown in the study UI
    position           # order inside that unit
    kanji, reading, meanings, sentence, explanation_md
    word_clip, sentence_clip
  entry_examples       # position 0 is the main sentence; later rows are extras
  word_marks           # known/flagged user state written by wordService
  word_service_settings

clips/
  words/wordNNN.mp3
  sentences/sentenceNNN.mp3
  generated_sentences/edge_tts/wordNNN_sentenceP.mp3
```

The browser-facing word number maps to `entries.source_index`, not to a JSON
array offset. When a word is wrong in the UI, inspect the matching `entries`
row and its `entry_examples` first. If corrected example text had generated
audio, clear that example's `audio_clip` so the service can regenerate audio
from the corrected sentence.

## Target Layout

When hardcoded legacy paths are retired, use this shape:

```text
N2Vocabulary/
├── audio/                  # source audio
├── json/                   # source OCR JSON
├── parse/                  # parser docs/source project
├── data/                   # canonical and normalized JSON
├── clips/                  # current service-facing audio clips
├── work/                   # mappings, audits, reviews, repair manifests
├── cache/                  # Whisper/temporary/regenerable files
├── dist/                   # final HTML exports and Anki decks
├── skills/                 # reusable workflow skills and scripts
├── wordService/            # local word-study service
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

In this repo, place those folders under `skills/`. Keep each skill concrete. `skills/cutTwice/` should only cut/transcribe audio clips. `skills/makeAnkiCards/` should only build/check/export Anki decks. The local study runtime belongs in `wordService/rust/`.

When a skill grows too large, split it by product or decision surface. For example, audio cutting, clip audit, Anki building, and HTML rendering should be separate skills because they have different inputs, outputs, and validation checks.
