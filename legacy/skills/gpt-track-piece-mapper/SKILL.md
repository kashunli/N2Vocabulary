---
name: gpt-track-piece-mapper
description: Map one JLPT vocabulary audio track with GPT using ffmpeg-derived non-silence pieces, per-piece Whisper transcription, and an expected word/sentence list. Prefer this skill when only the unit-level word range is known, the current track's start index is known, the current track's end index must be discovered from the audio, every speech piece must be accounted for, and bridge splits inside a speech piece may be needed before downstream cutting.
---

# GPT Track Piece Mapper

Use this skill when GPT, not Python heuristics, should decide the mapping for one audio track.

This skill is for mapping only. GPT decides which speech pieces belong to each word and sentence clip. Existing local scripts still perform the actual cutting and audit.

## Primary Mode

The default workflow is `unit-bounded sequential mode`.

Use it when:

- the unit-level range is known,
- the current track's start index is known,
- the current track's exact end index is not known yet,
- the track audio is expected to contain a contiguous prefix of the remaining unit entries.

Keep `exact-window mode` as a supported fast path when the exact contiguous track range is already known.

## Minimum Input

Provide these three primary evidence inputs for either mode:

1. ffmpeg-derived non-silence pieces with timestamps.
2. A per-piece Whisper transcription for those non-silence pieces.
3. An expected vocab artifact containing:
   - `index`
   - `headword`
   - `reading`
   - `expected sentence`

Optional secondary sidecar files:

- A full-track transcription with timestamps.
- A silence-boundary dump for fallback cut review.
- Keep both outside the main prompt when possible and refer to their file paths instead.
- Use them only as fallback context when the per-piece ASR is garbled or a cut boundary needs manual review.

### Unit-Bounded Sequential Mode

Provide these additional inputs:

- `unit_start_index`
- `unit_end_index`
- `current_track_start_index`
- one unit-level entries file containing every candidate entry in the known unit range

The unit-level entries file is a candidate list, not proof that every listed entry appears on the current track.

### Exact-Window Mode

Provide the exact contiguous entry list or exact `start-end` range for the track. In this mode, the selected entries are the complete contents of the track window.

## Core Rule

Treat ffmpeg non-silence pieces and their per-piece transcriptions as the primary evidence.

- Every non-silence piece in the selected run must be accounted for.
- Each non-silence piece should be consumed exactly once in the final mapping.
- Final clips should not overlap.
- in every audio track, word-sentence shall always be in order like the expected entries , no word/sentence/entry shall be jumped(without audio)
- Prefer assigning whole pieces to an item.
- If a piece is ambiguous, bias toward attaching it to the beginning or end of an adjacent item and explain that in `note`.
- In `unit-bounded sequential mode`, the returned indices must form one contiguous run that starts at `current_track_start_index`.
- In `unit-bounded sequential mode`, unused candidate entries are allowed only after the final returned index because they belong to later tracks.
- In `exact-window mode`, trust the exact selected range strongly:
  - no extra entries
  - no missing entries
  - no repetition
  - each entry follows `word` then `sentence`

## Workflow

### Unit-Bounded Sequential Mode

1. Gather the speech pieces and per-piece transcriptions for one track.
2. Prepare one unit-level candidate file covering the known unit range.
3. Tell GPT the known unit range and the known start index for the current track.
4. Tell GPT that the current track contains a contiguous sequence starting at `current_track_start_index`.
5. Require GPT to map that contiguous sequence from the beginning of the candidate list for this track and stop where the audio actually stops.
6. Assign every speech piece to a word clip, a sentence clip, or an explicit bridge boundary between adjacent items.
7. Determine the final entry actually spoken on this track from the audio.
8. Use the last item's `index` from the returned JSON as the boundary for the next track.

### Exact-Window Mode

1. Gather the speech pieces and per-piece transcriptions.
2. If the caller already knows the exact contiguous entry range on this track, treat that range as fixed and map within it only.
3. Assign every speech piece to a word clip, a sentence clip, or an explicit bridge boundary between adjacent items.
4. Prefer real silence edges for final cut boundaries.
5. Only use an intra-piece split when silence detection clearly failed to separate adjacent items.
6. When you use an intra-piece split, mark the affected clip with `bridge_split`.
7. Return mapping JSON for downstream cutting.

## Determine The Last Word On This Track

In `unit-bounded sequential mode`, GPT has two jobs:

1. map each speech piece to the correct `word` or `sentence` clip,
2. identify the final vocabulary entry actually spoken on the current track.

Practical rule:

- the final JSON array must stay ordered and contiguous,
- the last JSON item's `index` is the discovered end of the current track,
- the next track starts at `last_index + 1`,
- once the end is known, the operator can derive the exact per-track entries subset for the downstream cutter,
- no new output schema is required.

## Prompt Contract

### Unit-Bounded Sequential Prompt

Do not tell GPT that the track covers an exact `X-Y` range unless the end is already known.

Instead, use wording like this:

```text
This track starts at index 511 and continues with a contiguous sequence from the Unit 6 candidate list.
The candidate file `output/unit6_entries/unit6_511_580.json` contains every expected Unit 6 entry from 511 to 580.
Map a contiguous prefix beginning at index 511.
Unused candidate entries after the final mapped index are allowed because they may belong to later tracks.
Determine the final spoken entry on this track from the audio. The last JSON item's index becomes the boundary for the next track.
Every non-silence piece on this track must still be assigned exactly once.
```

This is the key difference from `exact-window mode`: the candidate list is a continuation list, not a claim that every listed entry appears on the current track.

### Exact-Window Prompt

When the track coverage is known exactly, it is still correct to say:

- this track covers exactly indices `X-Y`,
- there are no extra entries before or after that range,
- the entries occur in exact order,
- each entry is `word` then `sentence`.

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

Additional rules:

- In `unit-bounded sequential mode`, the returned indices must be contiguous and must start at `current_track_start_index`.
- In `unit-bounded sequential mode`, the final item's `index` is the discovered end of the current track.
- Each `piece_id` should appear only once across the final JSON.
- Final clip spans should be non-overlapping.

Read [references/mapping-schema.md](D:/n2Prepare/materialToLearn/N2Vocabulary/gpt-track-piece-mapper/references/mapping-schema.md) for the exact JSON shape and bridge examples.

## Unit 6 Sequential Example

Concrete verified facts in this repo:

- Unit 6 candidate range: `511-580`
- Unit 6 tracks present: `audio/Unit6 副詞A＋接続詞/39 1-39.mp3` through `43 1-43.mp3`
- Track 39 starts at `511`

Recommended operator flow:

1. Prepare one candidate file for all Unit 6 entries, for example `output/unit6_entries/unit6_511_580.json`.
2. Run Track 39 with `current_track_start_index=511`.
3. Let GPT map a contiguous prefix from the Unit 6 candidate file and discover Track 39's final index.
4. Start Track 40 at `last_index(track39) + 1`.
5. Continue the same carry rule through Tracks 41, 42, and 43.
6. On the final track, allow the candidate tail to remain unused if the audio ends before the unit ceiling or other unit metadata proves an earlier stop.

## Recommended Local Commands

Use local scripts only to prepare inputs and apply the finished mapping.

### Exact-Window Mode

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

### Unit-Bounded Sequential Mode

The current local helper script still emits exact-range prompt wording, so do not send its prompt text to GPT unchanged for this mode.

Instead:

1. use the existing tooling to prepare the track evidence:
   - non-silence pieces
   - per-piece transcripts
   - optional full-track and silence sidecars
2. prepare a unit-level candidate file such as `output/unit6_entries/unit6_511_580.json`
3. build a custom GPT prompt that:
   - references the candidate file,
   - states the known `current_track_start_index`,
   - requires a contiguous prefix from that start,
   - allows unused entries only after the final mapped index
4. once GPT returns the mapping JSON, derive the exact per-track entries subset from the returned first and last indices
5. apply the mapping with the normal downstream cutter flow using that exact per-track subset

## Practical Rules

- Use per-piece transcript semantics first, speech pieces second, and raw timestamps third.
- Use full-track timestamps only as fallback context; they are often too noisy to drive the mapping directly.
- Keep bulky fallback context such as full-track segment dumps and silence-boundary dumps in sidecar files, then refer to those files from the prompt instead of pasting them inline.
- In `unit-bounded sequential mode`, candidate files may be larger than one track. The track audio should still be mapped one track at a time.
- In `unit-bounded sequential mode`, do not force candidate entries after the audio clearly ends.
- In `exact-window mode`, treat order as a hard constraint:
  - contiguous indices only
  - no extra items before or after the range
  - no repetition
  - `word` then `sentence` for each entry
- Each `piece_id` should appear only once across the final JSON.
- Final clip spans should be non-overlapping.
- Do not silently discard any speech piece.
- Prefer whole-piece assignment over mid-piece cuts.
- Use `bridge_split` only when a true adjacent-item bridge is present.
- The actual mapped audio run should stay small enough that GPT can reason about every piece, usually about `10-20` entries even if the candidate file is larger.
