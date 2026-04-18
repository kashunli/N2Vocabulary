# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **JLPT N2 Vocabulary digitalization and Anki deck pipeline**. It extracts vocabulary from a scanned Japanese PDF textbook (`N2語彙トレーニング.pdf`), aligns it with audio tracks, and produces interactive study materials and Anki flashcard decks.

The project has two major completed pipelines:
1. **PDF → JSON → Audio Alignment** — OCR the scanned book, parse into structured JSON, cut word/sentence audio clips from MP3 tracks
2. **Vocabulary DB → AI Explanations → Anki Decks** — Generate sentence-level AI explanations for all 1142 vocabulary entries, then export as two Anki decks

## Directory Structure

```
N2Vocabulary/
├── parse/
│   ├── N2語彙トレーニング.pdf     ← source textbook
│   ├── scripts/                 ← all Python scripts
│   │   ├── parse_book.py        ← OCR markdown → structured JSON
│   │   ├── assign_track_clips.py← main audio clip extraction (Whisper + ffmpeg)
│   │   ├── deduce_boundary_clips.py ← recover unmatched clips
│   │   ├── merge_assigned_clips.py  ← merge clip paths into vocabulary DB
│   │   ├── make_clean_db.py     ← rebuild vocabulary_db.json from combined JSON
│   │   ├── make_anki.py         ← build N2Words.apkg
│   │   ├── make_anki_listening.py ← build N2Words_listening.apkg
│   │   ├── make_html.py         ← generate dashboard.html
│   │   ├── merge_explanations.py    ← merge AI explanation batches into DB
│   │   ├── dump_explanation_batch.py ← print next unexplained entries
│   │   ├── build_vocab_audio_dataset.py
│   │   ├── audit_review_candidates.py ← auto-approve audio matches
│   │   └── pipeline/            ← core audio utilities
│   │       ├── audio.py         ← cut_clip, detect_nonsilent_chunks, transcribe_track
│   │       ├── align.py         ← alignment algorithms, gap recovery
│   │       ├── vocab.py, text.py, output.py, models.py
│   ├── structured/              ← page-level parsed JSON from parse_book.py
│   └── pages_8_15_schema/       ← reference schema documentation
├── json/                        ← OCR output: page_001.json … page_100+ (vocab content)
├── audio/                       ← source MP3 tracks organized by Unit
├── output/
│   ├── vocabulary_combined.json ← master vocabulary database (1142 entries)
│   ├── vocabulary_db.json       ← clean DB with clip paths + explanations
│   ├── clips/                   ← cut word*.mp3 and sentence*.mp3 per unit
│   ├── review_assigned.json     ← audio alignment results with match scores
│   ├── N2Words.apkg             ← word-centered Anki deck
│   └── N2Words_listening.apkg   ← sentence-listening Anki deck (all 1142 explained)
├── jlpt-audio-cutter/           ← Claude Code skill for audio clip operations
├── tools/whispercpp-windows/    ← whisper-cli.exe + DLLs + ggml models (Vulkan GPU backend)
│   ├── whisper-cli.exe          ← whisper.cpp binary (Vulkan-enabled, built from source)
│   ├── ggml-vulkan.dll         ← Vulkan GPU runtime for AMD RX 6900/6950 XT
│   ├── ggml.dll, ggml-base.dll, ggml-cpu.dll, whisper.dll
│   ├── ggml-medium.bin         ← medium model (~1.5 GB)
│   └── ggml-large-v3-turbo.bin ← large-v3-turbo model (~1.6 GB, better quality)
├── dashboard.html               ← interactive vocabulary review dashboard
└── RESUME.md                    ← detailed project history and decisions
```

## Common Commands

### Audio Clip Extraction

```bash
# Single track (openai/Python whisper backend — CPU only)
python3 -u parse/scripts/assign_track_clips.py \
    --track "audio/Unit3 形容詞A/19 1-19.mp3" \
    --start 245 --end 255 \
    --silence-duration 0.25 --device cpu

# Single track (whisper.cpp Vulkan GPU backend — AMD RX 6900/6950 XT)
python3 -u parse/scripts/align_track_by_llm.py \
    --backend whisper_cpp \
    --wcpp-binary tools/whispercpp-windows/whisper-cli.exe \
    --wcpp-model tools/whispercpp-windows/ggml-medium.bin \
    --track "audio/..." --entries-json /tmp/entries.json

# Smoke test the whisper.cpp backend
python3 parse/scripts/align_track_by_llm.py --backend whisper_cpp \
    --wcpp-binary tools/whispercpp-windows/whisper-cli.exe \
    --wcpp-model tools/whispercpp-windows/ggml-medium.bin \
    --backend-info

# Multiple tracks via config
python3 -u parse/scripts/assign_track_clips.py \
    --config parse/scripts/track_ranges.json \
    --silence-duration 0.25 --device cpu

# Merge results into vocabulary DB
python3 parse/scripts/merge_assigned_clips.py output/review_assigned.json
```

### Rebuild Database and Decks

```bash
# Rebuild clean DB from combined vocabulary
python3 parse/scripts/make_clean_db.py

# Rebuild Anki decks
python3 parse/scripts/make_anki.py
python3 parse/scripts/make_anki_listening.py

# Regenerate HTML dashboard
python3 parse/scripts/make_html.py
```

### Explanation Batches (for AI-generated sentence explanations)

```bash
# Dump next batch of unexplained entries
python3 parse/scripts/dump_explanation_batch.py --skip-done

# Merge completed explanations into DB
python3 parse/scripts/merge_explanations.py <batch_file.json>
```

### Parse Book (OCR → JSON)

```bash
# Parse all pages
python3 parse/scripts/parse_book.py --stats

# Parse specific pages
python3 parse/scripts/parse_book.py --page 9 --page 10 --clean
```

## Key Parameters for Audio Processing

| Parameter | Default | When to change |
|-----------|---------|----------------|
| `--silence-duration` | 0.18 | **Use 0.25** for Japanese — avoids cutting mid-word on final consonants |
| `--silence-noise` | -32dB | Lower for noisy audio; raise for clean studio |
| `--device` | cpu | `cuda` if NVIDIA GPU; **Vulkan auto-detected** for AMD via `--backend whisper_cpp` |
| `--backend` | openai | **`whisper_cpp`** for Vulkan GPU on AMD RX 6900/6950 XT |
| `WHISPER_CPP_BIN` | env | `tools/whispercpp-windows/whisper-cli.exe` |
| `WHISPER_CPP_MODEL` | env | `tools/whispercpp-windows/ggml-medium.bin` (or `ggml-large-v3-turbo.bin`) |

## Architecture

### Pipeline 1: PDF → Structured JSON → Audio Clips

1. **OCR** (external, Aliyun qwen-vl-ocr) renders PDF pages → markdown under `ocr/pages/page-*/markdown.md`
2. **Parse** (`parse_book.py`) converts OCR markdown → page-level JSON in `json/`
3. **Combine** → `output/vocabulary_combined.json` (master vocab with meanings, examples, relations)
4. **Audio alignment** (`assign_track_clips.py`):
   - ffmpeg silence detection splits MP3 tracks into speech chunks
   - Whisper transcribes each chunk with constrained vocabulary search
   - Forward-search algorithm matches transcripts to vocab entries
   - Gap recovery handles unmatched entries between matched neighbors
5. **Merge** (`merge_assigned_clips.py`) updates clip paths into vocabulary DB

### Pipeline 2: Explanations → Anki Decks

1. **Dump batches** (`dump_explanation_batch.py`) outputs entries needing AI explanations
2. **Generate explanations** (AI-assisted, per batch) in format: `phrase = "translation" — grammar explained`
3. **Merge** (`merge_explanations.py`) integrates batches into `vocabulary_db.json`
4. **Build decks** (`make_anki.py`, `make_anki_listening.py`) → `.apkg` files

### Audio Match Methods

| Method | When | Reliability |
|--------|------|-------------|
| `whisper` | Direct match | High |
| `silence_boundary` | Single entry, split by silence | Good |
| `gap_boundary` | Multiple entries, boundaries from gaps | Good |
| `shared_region` | Too few chunks — shared | Low, needs review |
| `single_chunk` | One chunk for both | Needs review |

## Current Status (as of 2026-04-11)

- **1142/1142 entries** have AI explanations (100% complete)
- Both Anki decks built and deployed to `D:\n2Prepare\ankiCardsToBuilt\`
- Audio alignment: 737 matched, remaining entries need review
- Use `output/review_still_needs_human.json` as the unresolved review queue

## Important Notes

- `--silence-duration 0.25` is critical for Japanese audio — the default 0.18s cuts mid-word
- Whisper often transcribes kanji as kana/hiragana — use kana-based comparison for scoring
- Misaligned anchor entries cascade forward — check neighboring entries when diagnosing
- The Windows GPU backend uses `--backend whisper_cpp` with Vulkan — binary at `tools/whispercpp-windows/whisper-cli.exe`, model at `tools/whispercpp-windows/ggml-medium.bin`
- DLLs (`ggml.dll`, `ggml-vulkan.dll`, `ggml-cpu.dll`, `ggml-base.dll`, `whisper.dll`) must be co-located with `whisper-cli.exe` in `tools/whispercpp-windows/`
- Source code for the Vulkan build is at `D:\wcpp\whisper.cpp-src` (built with `cmake -B build -G Ninja -DGGML_VULKAN=1` using VS 2022)
- Read `RESUME.md` for full project history and design decisions
- The `jlpt-audio-cutter/` directory contains a Claude Code skill — read `SKILL.md` for audio operations
