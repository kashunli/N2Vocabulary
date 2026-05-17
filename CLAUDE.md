# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **JLPT N2 Vocabulary digitalization and Anki deck pipeline**. It extracts vocabulary from a scanned Japanese PDF textbook (`parse/N2語彙トレーニング.pdf`), aligns it with audio tracks, and produces interactive study materials and Anki flashcard decks.

**Current audio-cutting pipeline: `skills/cutTwice/`** — a pair-first silence-based cutter with whisper.cpp transcription. See `skills/cutTwice/SKILL.md` for invocation.

Earlier approaches (the `align_track_by_llm.py` + `parse/scripts/` Python pipeline, plus older skills) now live under `legacy/` as reference material — see `legacy/README.md`.

Current docs:

- `README.md` — project overview and folder map.
- `AGENTS.md` — project memory and AI-maintainable coding principles.
- `docs/ARCHITECTURE.md` — source/data/work/cache/dist model.
- `docs/RUNBOOK.md` — current rebuild commands.
- `docs/DECISIONS.md` — durable cleanup and workflow decisions.

## Directory Structure

```
N2Vocabulary/
├── skills/                      ← project-local skills gathered for review/reuse
│   ├── cutTwice/                ← CURRENT audio-cutting skill (SKILL.md + scripts)
│   ├── makeAnkiCards/           ← CURRENT Anki deck workflow
│   ├── batch-japanese-sentence-explanations/
│   ├── japanese-sentence-explanation-skill/
│   └── aliyun-openai-compatible-api/
├── audio/                       ← source MP3s organized by Unit
├── json/                        ← OCR output: page-level vocab JSON
├── clips/                       ← current cut clips (pair/word/sentence per track)
├── db/                          ← SQLite database layer (connect, import, migrations)
├── docs/                        ← current architecture/runbook/decisions
├── output/
│   ├── n2vocab.sqlite           ← master vocabulary SQLite DB (1142 entries)
│   ├── alignment/               ← grouped alignment artifacts
│   │   ├── review/              ← review_unit*_track_*.json
│   │   ├── entries/             ← per-unit entry fragments
│   │   ├── mappings/            ← per-unit audio mappings
│   │   └── audits/              ← clip audit logs + transcript caches
│   ├── explanations/            ← AI sentence explanations per unit
│   │   └── batches/             ← explanation batch dump .txt files
│   ├── clips/                   ← older clip outputs (gitignored)
│   ├── N2Words.apkg             ← word-centered Anki deck
│   └── N2Words_listening.apkg   ← sentence-listening Anki deck
├── wordsAndExerciseInHtml/      ← static HTML words and exercises
├── legacy/                      ← archived code and data — reference only
│   ├── scripts/                 ← align_track_by_llm.py + align/ module
│   ├── skills/                  ← full-unit-cutter, gpt-track-piece-mapper
│   ├── parse-scripts/           ← old parse/scripts/ Python pipeline
│   ├── backups/                 ← vocabulary_*.json.bk snapshots
│   └── oldClips/                ← 80 MB pre-recut audio archive (gitignored)
├── parse/                       ← parser docs/project files, flattened into root Git
├── tools/whispercpp-windows/    ← whisper-cli.exe + DLLs + ggml models (Vulkan)
├── updates/                     ← dated change records and cleanup notes
├── dashboard.html               ← interactive vocabulary review dashboard
├── marks_server.py              ← background word-marking server
├── AGENTS.md                    ← project memory for AI agents
├── RESUME.md                    ← project history and design decisions
└── CLAUDE.md                    ← this file
```

## Working conventions

**Preferred authoring style**: self-contained skills (a `SKILL.md` describing CLI + intent, bundled with its scripts) rather than loose script directories. When a new task recurs, extract it into a skill.

**AI-first repository design**: this project is usually operated by an AI agent on the user's behalf. Optimize for small, concrete workflow folders with explicit input/output/cache contracts rather than broad human-memory-based script collections.

**Legacy as library**: when building a new skill, mine `legacy/parse-scripts/` and `legacy/scripts/` for patterns (OCR parsing, Anki deck building, Whisper alignment, clip auditing). Do not invoke those scripts directly — copy the relevant logic into the new skill.

**Folder contract for skills**: skill scripts should accept explicit input and output paths. In this repo, current audio inputs come from `audio/`, durable cut clips go to root `clips/`, repair/review work belongs under `work/` or current compatibility folder `output/alignment/`, and cache/scratch belongs under ignored cache locations.

## Current pipelines

### Audio cutting — skills/cutTwice/
See `skills/cutTwice/SKILL.md`. Two modes:
- **Strict count** (`--expected N`): threshold-search until exactly N pairs.
- **Just-cut** (`--just-cut`): default 0.9 s silence, one pass, keep whatever count.

### Anki deck building
The current deck builders live in `skills/makeAnkiCards/scripts/`. They read `output/n2vocab.sqlite` plus `clips/` and write the `.apkg` outputs under `output/` by default.

### Explanations workflow
Batch AI sentence explanations live in `skills/batch-japanese-sentence-explanations/`. The reusable single-sentence explanation skill is preserved under `skills/japanese-sentence-explanation-skill/` for later review.

## Key parameters

| Parameter | Default | Notes |
|-----------|---------|-------|
| `--silence-duration` | 0.9 s (cutTwice just-cut) / 0.25 s (legacy) | Japanese audio needs generous silence to avoid cutting mid-word on final consonants |
| `--noise-db` | -35 dB | Lower (more negative) for noisy audio |
| Whisper backend | whisper.cpp Vulkan | AMD RX 6900/6950 XT via `tools/whispercpp-windows/whisper-cli.exe` |
| Whisper model | `ggml-large-v3-turbo.bin` | Preferred; `ggml-medium.bin` is a smaller fallback |

## Status (2026-05-17)

- 1142/1142 entries have AI explanations (100%).
- Both Anki decks built and deployed to `D:\n2Prepare\ankiCardsToBuilt\`.
- Audio alignment in progress — `output/alignment/review/` holds per-track results.
- Project directory reorganized: legacy code archived, output/ grouped by purpose.

## Important notes

- `tools/whispercpp-windows/` DLLs (`ggml*.dll`, `whisper.dll`) must stay co-located with `whisper-cli.exe`.
- Vulkan build source lives outside the repo at `D:\wcpp\whisper.cpp-src` (`cmake -B build -G Ninja -DGGML_VULKAN=1`).
- Whisper often transcribes kanji as kana/hiragana — any scoring logic should compare on kana.
- `RESUME.md` has the full project history.
