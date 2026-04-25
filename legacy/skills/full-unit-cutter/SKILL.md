---
name: full-unit-cutter
description: End-to-end workflow to cut word and sentence audio clips for all tracks in a JLPT vocabulary unit. Self-contained — no research needed. Covers source locations, whisper.cpp commands, mapping generation, clip cutting, and DB merging.
---

# Full Unit Cutter

Self-contained guide to cut word + sentence audio clips for every track in a unit. No prior research needed — all paths, commands, and rules are documented here.

## What You Need (Sources)

### 1. Audio tracks
- Location: `audio/UnitX <name>/`
- Naming: `<track_number> <N>-<track_number>.mp3` (e.g. `39 1-39.mp3`)
- Each unit has multiple tracks (e.g. Unit 6 has tracks 39-43).

### 2. Vocabulary entries for the unit
- Source: `output/vocabulary_combined.json` — master DB with all entries.
- Extract a per-unit candidate file (indices covering the whole unit):
  ```bash
  python3 -c "
  import json
  db = json.load(open('output/vocabulary_combined.json', encoding='utf-8'))
  unit_entries = [e for e in db if e['unit_number'] == 6]
  # Build a minimal entries file with index, headword, reading, expected_sentence
  entries = []
  for e in unit_entries:
      entries.append({
          'index': e['index'],
          'headword': e['headword'],
          'reading': e['reading'],
          'expected_sentence': e['example_sentence'],
      })
  json.dump(entries, open('output/unit6_entries/unit6_511_580.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
  print(f'Wrote {len(entries)} entries, indices {entries[0][\"index\"]}-{entries[-1][\"index\"]}')
  "
  ```
- Output: `output/unitX_entries/unitX_<first>_<last>.json`

### 3. Whisper.cpp backend (Vulkan GPU)
- Binary: `tools/whispercpp-windows/whisper-cli.exe`
- Model: `tools/whispercpp-windows/ggml-large-v3-turbo.bin` (preferred) or `ggml-medium.bin`
- DLLs must be co-located in `tools/whispercpp-windows/`.

### 4. Python scripts
- `parse/scripts/align_track_by_llm.py` — main CLI: transcription, silence detection, prompt building, clip cutting.
- `parse/scripts/merge_assigned_clips.py` — merges clip paths from review JSONs into `vocabulary_db.json`.
- Supporting modules in `parse/scripts/pipeline/` (align.py, audio.py, etc.).

## The Workflow (Per Unit)

### Phase 1: Prepare per-track entries subsets

After Phase 2 discovers boundaries, you'll know which entries belong to each track. Initially, prepare one candidate file covering the whole unit (see "Sources" section above).

### Phase 2: Process each track sequentially

For each track in the unit (e.g. Track 39, 40, 41, 42, 43 for Unit 6):

#### Step 2a: Generate the mapping prompt

```bash
python3 parse/scripts/align_track_by_llm.py \
  --backend whisper_cpp \
  --wcpp-binary tools/whispercpp-windows/whisper-cli.exe \
  --wcpp-model tools/whispercpp-windows/ggml-large-v3-turbo.bin \
  --track "audio/Unit6 副詞A＋接続詞/39 1-39.mp3" \
  --entries-json output/unit6_entries/unit6_511_580.json \
  --mapping-mode unit-sequential \
  --current-track-start-index 511 \
  --prompt-only
```

This prints a long prompt containing:
- ffmpeg-derived non-silence pieces with timestamps
- per-piece Whisper transcriptions
- vocabulary entry list
- silence boundary sidecar references

**Important**: The script's built-in prompt uses `exact-window` wording even in `unit-sequential` mode. Do NOT use it verbatim. Rewrite the prompt using the template in the "Prompt Template" section below.

#### Step 2b: Analyze pieces and create the mapping yourself

Since we're doing the mapping ourselves (no external GPT), analyze the printed evidence:

1. Read the piece transcriptions and match them to vocabulary entries in order.
2. For each entry, identify which pieces contain the **word** (headword reading) and which contain the **example sentence**.
3. Build a mapping JSON (see "Mapping Schema" below).
4. Save to `output/unitX_mappings/mapping_<track>.json`.

**Mapping rules:**
- Every piece ID must appear in exactly ONE clip (word or sentence) across the entire mapping.
- Word clip comes first, sentence clip comes second for each entry.
- Prefer assigning whole pieces to clips. Only split inside a piece when one piece clearly contains the tail of entry A and head of entry B — mark with `"bridge_split"`.
- **Word+sentence fused in one piece (silence detection missed the gap):** When ffmpeg silence detection doesn't split the word and its sentence into separate pieces, they land as one combined piece. In this case, consult the **full-track Whisper segments** file (`output/whisper_cache/<track>_segments.json`) — it contains fine-grained per-word timestamps. Find the segment where the word ends and the sentence begins, then use that segment's `end` timestamp as the bridge cut point. Mark both clips with `"bridge_split"`. Example: if piece 0 contains both "最も" and its sentence, and the full-track segments show "も" ending at 2.11 and the sentence starting from 2.11, set word `end: 2.11` and sentence `start: 2.11`, both with `"bridge_split"`.
- If a word has no separate piece AND the full-track segments don't give a usable boundary (the word is too short or garbled), use `"piece_ids": []` for the word with flags `["word_in_sentence_no_separate_piece"]` and a best-effort sub-range timestamp.
- ASR errors are common — match by reading similarity and sentence context, not exact text.
- Handle repeated word variants: if audio says the word twice (e.g. both にやにや and にやりと), assign both pieces to the word clip with flag `["word_repeated"]`.
- Handle extraneous audio (YouTube outros, spurious content) by attaching to adjacent clip with `extraneous_content_at_start` flag.

#### Step 2c: Apply the mapping to cut clips

```bash
python3 parse/scripts/align_track_by_llm.py \
  --backend whisper_cpp \
  --wcpp-binary tools/whispercpp-windows/whisper-cli.exe \
  --wcpp-model tools/whispercpp-windows/ggml-large-v3-turbo.bin \
  --track "audio/Unit6 副詞A＋接続詞/39 1-39.mp3" \
  --entries-json output/unit6_entries/unit6_511_580.json \
  --mapping-mode unit-sequential \
  --current-track-start-index 511 \
  --llm-json output/unit6_mappings/mapping_39.json \
  --output output/review_unit6_track_39.json \
  --unit 6 --rescore
```

This:
1. Transcribes the full track (or reads from cache).
2. Detects silence boundaries with ffmpeg.
3. Cuts MP3 clips to `output/clips/unit06/` (word511.mp3, sentence511.mp3, etc.).
4. Writes a review JSON with scores.
5. Reports the discovered end index (e.g. "Suggested next track start: 525").

#### Step 2d: Carry forward the index

The next track starts at `last_discovered_index + 1`. For Unit 6:
- Track 39: start 511 → discovered end 524
- Track 40: start 525 → discovered end 539
- Track 41: start 540 → discovered end 556
- Track 42: start 557 → discovered end 572
- Track 43: start 573 → discovered end 580

Repeat Steps 2a-2d for each track until the unit is done.

### Phase 3: Merge into vocabulary DB

After all tracks are processed:

```bash
python3 parse/scripts/merge_assigned_clips.py output/review_unit6_track_39.json
python3 parse/scripts/merge_assigned_clips.py output/review_unit6_track_40.json
python3 parse/scripts/merge_assigned_clips.py output/review_unit6_track_41.json
python3 parse/scripts/merge_assigned_clips.py output/review_unit6_track_42.json
python3 parse/scripts/merge_assigned_clips.py output/review_unit6_track_43.json
```

Each command updates `output/vocabulary_db.json` with clip paths for that track's entries.

### Phase 4: Verify

```bash
python3 -c "
import json
db = json.load(open('output/vocabulary_db.json', encoding='utf-8'))
unit6 = [e for e in db if e.get('unit_number') == 6]
has_clips = [e for e in unit6 if e.get('word_clip') and e.get('sentence_clip')]
no_clips = [e for e in unit6 if not e.get('word_clip') or not e.get('sentence_clip')]
print(f'Unit 6: {len(has_clips)}/{len(unit6)} entries have clips')
if no_clips:
    print(f'Missing clips for indices: {[e[\"index\"] for e in no_clips]}')
"
```

### Phase 5 (optional): Rebuild Anki decks

```bash
python3 parse/scripts/make_anki.py
python3 parse/scripts/make_anki_listening.py
python3 parse/scripts/make_html.py
```

## Mapping Schema

Each mapping JSON is an array of objects:

```json
{
  "index": 511,
  "word": {
    "start": 0.607,
    "end": 1.263,
    "piece_ids": [0],
    "flags": []
  },
  "sentence": {
    "start": 1.952,
    "end": 5.873,
    "piece_ids": [1, 2],
    "flags": []
  },
  "flags": [],
  "note": "Brief explanation of the mapping decision."
}
```

### Flags

| Flag | On | Meaning |
|------|-----|---------|
| `bridge_split` | word or sentence | Split inside a piece between adjacent entries |
| `word_repeated` | entry-level `flags` | Audio repeated the word variant(s) |
| `word_in_sentence_no_separate_piece` | word | Word has no dedicated piece; use sub-range timestamp |
| `extraneous_content_at_start` | sentence | Spurious/outro audio attached at sentence start |
| `trailing_audio` | sentence | Very short trailing micro-pieces at end |

### Timestamp rules
- When `piece_ids` is non-empty, `start` and `end` should match the boundary timestamps of the first/last piece in the list.
- When `piece_ids` is empty (word_in_sentence case), use a sub-range timestamp within the sentence piece.
- Timestamps will be snapped to nearest silence edge by the cutter.

## Prompt Template (for self-analysis)

When you need to analyze pieces yourself, gather the evidence from the script output and use this structure:

```
Track: <track_path>
Unit X, entries <first>-<last>
Current track starts at index <N>.

--- PIECE TRANSCRIPTS ---
Piece 0: [<start>→<end>] "<transcription>"
Piece 1: [<start>→<end>] "<transcription>"
...

--- CANDIDATE ENTRIES ---
Index <N>: <headword> (<reading>) — <expected_sentence>
Index <N+1>: ...
...

Task: Map every piece to exactly one word or sentence clip.
- Each entry gets a word clip and a sentence clip.
- Every piece_id must appear exactly once.
- Indices must be contiguous starting from <N>.
- Determine the final spoken entry from the audio evidence.
- Note ASR errors and explain mapping decisions.
```

## Common ASR Error Patterns

| Expected | Whisper says | Why |
|----------|-------------|-----|
| にやにや | にゃにゃ | Vowel devoicing |
| すなわち | つながち | Sibilant confusion |
| 至急 | 地球 / 子宮 | Kanji reading misrecognition |
| さらに | サラニ | Katakana transcription |
| ところが | どころが | Voiced/unvoiced confusion |
| わりに | ありと／バリに | Context-dependent reading |

Match by **reading similarity + sentence context + sequence position**, not exact text.

## Key Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| `--silence-duration` | 0.25 | Critical for Japanese — 0.18 cuts mid-word |
| `--silence-noise` | -32dB | Default; lower for noisy audio |
| `--backend` | whisper_cpp | Vulkan GPU on AMD RX 6900/6950 XT |
| `--wcpp-model` | ggml-large-v3-turbo.bin | Best quality; ggml-medium.bin is faster |
| `--rescore` | flag | Re-transcribes cut clips for quality scores |

## Quick Reference: Full Unit 6 Commands

```bash
# Track 39 (entries 511-524)
python3 parse/scripts/align_track_by_llm.py \
  --backend whisper_cpp \
  --wcpp-binary tools/whispercpp-windows/whisper-cli.exe \
  --wcpp-model tools/whispercpp-windows/ggml-large-v3-turbo.bin \
  --track "audio/Unit6 副詞A＋接続詞/39 1-39.mp3" \
  --entries-json output/unit6_entries/unit6_511_580.json \
  --mapping-mode unit-sequential \
  --current-track-start-index 511 \
  --llm-json output/unit6_mappings/mapping_39.json \
  --output output/review_unit6_track_39.json \
  --unit 6 --rescore

# ... repeat for tracks 40-43 with updated start indices ...

# Merge all tracks
for f in output/review_unit6_track_*.json; do
  python3 parse/scripts/merge_assigned_clips.py "$f"
done
```

## Truth Hierarchy (Discovered from Unit 7, Track 44)

When mapping evidence conflicts, follow this priority order:

1. **Index in the entries file is most reliable** — if an index exists in the candidate list, it is the slot to fill. Assign audio to that index.
2. **What you hear in the audio (the prescription) is ground truth** — if the DB says 監督 but the audio says 栽培, assign the audio to the index slot anyway. The clip will be cut correctly even if the DB label is wrong. The DB label can be fixed later.
3. **Word-sentence pattern (word first, sentence second) is reliable** — use it to distinguish word vs sentence clips within a piece group.
4. **Sequence position is reliable** — entries appear in the audio in the same order as their indices.
5. **ASR transcription is least reliable** — match by reading similarity, sentence context, and sequence position, NOT exact text.

**Practical rule:** When the audio says word X but the DB entry at that index says word Y, assign the audio to that index slot. Don't skip the index or try to reassign to a different index. The index is the address; the audio fills it.

## DB Index Gaps

The `vocabulary_combined.json` may have missing indices (e.g. 592, 610, 639, 663-667, 670-675 in Unit 7). These are real entries that exist in the book's OCR data and are spoken in the audio, but were omitted from the combined DB during parsing.

**Symptom:** The `unit-sequential` validator rejects a mapping that jumps from 591 → 593 because indices must be contiguous.

**Resolution:**
1. Find the missing entry in the OCR data (`json/page_*.json`) using the index number.
2. Create a **track-specific entries file** (e.g. `output/unit7_entries/unit7_track44_581_598.json`) that includes the missing entry filled in from OCR.
3. Pass the track-specific entries file to `--entries-json` instead of the full unit file.
4. Include the filled-in index in your mapping JSON with its correct word/sentence pieces.

## Skill Review: Conflicting Principles

The following principles in this skill can conflict in edge cases. The resolution hierarchy above should be used.

| Conflicting principles | When it breaks | Resolution |
|------------------------|---------------|------------|
| "Trust global order" vs "Match by reading/context" | ASR mangles the word beyond recognition | Index position wins — assign by sequence, not by ASR text match |
| "Every piece must appear in exactly one clip" vs "Indices must be contiguous" | DB has missing indices (gaps) | Fill the gap from OCR data into a track-specific entries file |
| "Do not invent entries before the known start index" vs "Index is the address" | Audio has entries the DB doesn't have | The index from the entries file IS the slot. Assign audio to it regardless of content mismatch |
| "Unused entries allowed only after final mapped index" vs "DB gaps in middle" | Audio runs contiguously but DB has a hole | Not resolvable without filling the gap. See "DB Index Gaps" above |

## Reference Files

- [mapping-schema.md](references/mapping-schema.md) — detailed JSON schema and bridge examples
