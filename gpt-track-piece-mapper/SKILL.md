---
name: gpt-track-piece-mapper
description: Map one small JLPT vocabulary audio track window with GPT using full-track transcription, ffmpeg-derived non-silence pieces, and the expected word/sentence list. Use when GPT should decide the mapping for about 10-20 entries, every speech piece must be accounted for, and bridge splits inside a speech piece may be needed before downstream cutting.
---

# GPT Track Piece Mapper

Use this skill when GPT, not Python heuristics, should decide the mapping for one small audio track window.

This skill is for mapping only. GPT decides which speech pieces belong to each word and sentence clip. Existing local scripts still perform the actual cutting and audit.

## Minimum Input

Provide these three inputs:

1. A full-track or chosen-window transcription with timestamps.
2. ffmpeg-derived non-silence pieces with timestamps.
3. The expected vocab list for the run:
   - `index`
   - `headword`
   - `reading`
   - `expected sentence`

The skill supports two input modes:

- Exact-window mode:
  - the caller already knows the exact track window or exact entry list to map
- Rough-hint mode:
  - the caller provides a rough start point and approximate extent or item count
  - GPT first localizes the window, then maps it fully

## Core Rule

Treat ffmpeg non-silence pieces as the primary coverage units.

- Every non-silence piece in the selected run must be accounted for.
- Do not leave trailing closures like `った` or `って` unassigned.
- Prefer assigning whole pieces to an item.
- If a piece is ambiguous, bias toward attaching it to the beginning or end of an adjacent item and explain that in `note`.

## Workflow

1. Gather the track transcription and silence pieces.
2. If the input is rough, localize the intended item run first.
3. Assign every speech piece to a word clip, a sentence clip, or an explicit bridge boundary between adjacent items.
4. Prefer real silence edges for final cut boundaries.
5. Only use an intra-piece split when silence detection clearly failed to separate adjacent items.
6. When you use an intra-piece split, mark the affected clip with `bridge_split`.
7. Return mapping JSON for downstream cutting.

## Boundary Rules

- Normal case:
  - prefer a real silence edge near the intended boundary
- Near-miss case:
  - if the best silence edge is slightly outside the nominal tolerance, still prefer that real silence edge
- Bridge case:
  - if one speech piece plausibly contains the tail of item A and the head of item B, you may split inside that piece
  - mark the affected clip with `bridge_split`
  - preserve the explicit GPT timestamp for the affected boundary

## Output Contract

Return one JSON array. Each item should contain:

- `index`
- `word`
- `sentence`
- `note`
- optional `flags`

For `word` and `sentence`, include:

- `start`
- `end`
- `piece_ids`
- optional `flags`
- optional `preserve_boundaries`

Read [references/mapping-schema.md](D:/n2Prepare/materialToLearn/N2Vocabulary/gpt-track-piece-mapper/references/mapping-schema.md) for the exact JSON shape and bridge examples.

## Recommended Local Commands

Use local scripts only to prepare inputs and apply the finished mapping.

Build a GPT prompt from an exact track run:

```bash
python parse/scripts/align_track_by_llm.py \
  --backend whisper_cpp \
  --wcpp-binary tools/whispercpp-windows/whisper-cli.exe \
  --wcpp-model tools/whispercpp-windows/ggml-large-v3-turbo.bin \
  --track "audio/Unit2 動詞A/16 1-16.mp3" \
  --entries-json output/unit2_entries/entries_16.json \
  --prompt-only
```

Apply a GPT-produced mapping JSON:

```bash
python parse/scripts/align_track_by_llm.py \
  --backend whisper_cpp \
  --wcpp-binary tools/whispercpp-windows/whisper-cli.exe \
  --wcpp-model tools/whispercpp-windows/ggml-large-v3-turbo.bin \
  --track "audio/Unit2 動詞A/16 1-16.mp3" \
  --entries-json output/unit2_entries/entries_16.json \
  --llm-json output/unit2_mappings/mapping_16.json \
  --output output/review_unit2_track_16.json \
  --unit 2 --rescore
```

## Practical Rules

- Use transcript semantics first, speech pieces second, and raw timestamps third.
- Do not silently discard any speech piece.
- Prefer whole-piece assignment over mid-piece cuts.
- Use `bridge_split` only when a true adjacent-item bridge is present.
- Keep the run small enough that GPT can reason about every piece, usually about `10-20` items.
