# Mapping Schema

The JSON format for track piece mappings, produced by the full-unit-cutter workflow.

## Top-level structure

A mapping is a JSON array. Each element represents one vocabulary entry:

```json
[
  {
    "index": 511,
    "word": { ... },
    "sentence": { ... },
    "flags": [],
    "note": "..."
  }
]
```

## Clip object (`word` and `sentence`)

```json
{
  "start": 0.607,
  "end": 1.263,
  "piece_ids": [0],
  "flags": []
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `start` | number | yes | Start timestamp in seconds. Snapped to nearest silence edge by the cutter. |
| `end` | number | yes | End timestamp in seconds. Snapped to nearest silence edge by the cutter. |
| `piece_ids` | array<int> | yes | List of piece IDs consumed by this clip. May be empty for `word_in_sentence_no_separate_piece` cases. |
| `flags` | array<string> | no | Clip-level flags: `bridge_split`. |

## Entry-level fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `index` | int | yes | Vocabulary entry index from the candidate file. |
| `word` | object | yes | Word clip definition. |
| `sentence` | object | yes | Sentence clip definition. |
| `flags` | array<string> | no | Entry-level flags: `word_repeated`. |
| `note` | string | yes | Free-text explanation of mapping decisions and ASR errors. |

## Flags

### `bridge_split` (clip-level)

Use when a single piece contains the tail of entry A and the head of entry B. Split inside the piece at a timestamp boundary.

```json
{
  "index": 42,
  "word": {
    "start": 10.0,
    "end": 11.234,
    "piece_ids": [5],
    "flags": ["bridge_split"]
  },
  ...
}
```

The piece ID (e.g., `5`) appears only in this clip, not in the adjacent entry's clip. The `end` timestamp is an intra-piece split point, not a silence edge.

### `bridge_split` for word+sentence fused in one piece

When ffmpeg silence detection doesn't find a gap between the word and its sentence, they land as one combined piece. In this case, use the **full-track Whisper segments** file (`output/whisper_cache/<track>_segments.json`) to find the boundary. That file has fine-grained per-word timestamps — locate where the word's last segment ends and use that timestamp as the cut point between the word clip and the sentence clip.

Both the word's `end` and the sentence's `start` should share the same timestamp from the segment boundary:

```json
{
  "index": 511,
  "word": {
    "start": 0.607,
    "end": 2.11,
    "piece_ids": [0],
    "flags": ["bridge_split"]
  },
  "sentence": {
    "start": 2.11,
    "end": 5.873,
    "piece_ids": [0],
    "flags": ["bridge_split"]
  },
  "flags": [],
  "note": "Piece 0 contains both word and sentence — silence detection missed the gap. Cut point 2.11 taken from full-track segments: 'も' ends at 2.11, sentence begins immediately after."
}
```

Note: piece 0 appears in both clips — this is the ONLY case (besides inter-entry bridge splits) where a piece_id is duplicated. The `bridge_split` flag signals the cutter to use the intra-piece timestamp boundary.

**How to find the cut point:**
1. Open the full-track segments JSON for this track.
2. Find the segment that contains the word (search for the headword or its reading in the `text` field).
3. Take the `end` timestamp of the word's last segment — that is your bridge cut point.
4. If the word is split across multiple segments (e.g., "最" at 1.69-1.96, "も" at 1.96-2.11), use the last one's `end` (2.11).

### `word_repeated` (entry-level)

Use when the audio repeats multiple pronunciation variants of the same word. Assign all relevant pieces to the word clip.

```json
{
  "index": 556,
  "word": {
    "start": 108.408,
    "end": 110.758,
    "piece_ids": [49, 50],
    "flags": []
  },
  "flags": ["word_repeated"],
  "note": "Pieces 49-50 are にこにこ and にっこり (both word variants)."
}
```

### `word_in_sentence_no_separate_piece` (clip-level on word)

Use when the word has no dedicated speech piece — it only appears inside the sentence piece. Use a sub-range timestamp within the sentence piece.

```json
{
  "index": 519,
  "word": {
    "start": 57.8,
    "end": 58.2,
    "piece_ids": [],
    "flags": ["word_in_sentence_no_separate_piece"]
  },
  "sentence": {
    "start": 55.768,
    "end": 60.309,
    "piece_ids": [27, 28, 29, 30],
    "flags": []
  },
  ...
}
```

The word's `piece_ids` is empty — the piece (e.g., `29`) is consumed only by the sentence clip.

### `extraneous_content_at_start` (clip-level on sentence)

Use when spurious content (YouTube outros, ads, sign-offs) appears at the start of the sentence audio.

```json
{
  "sentence": {
    "start": 55.768,
    "end": 60.309,
    "piece_ids": [27, 28, 29, 30],
    "flags": ["extraneous_content_at_start"]
  },
  "note": "Pieces 27-28 are extraneous audio attached to sentence start boundary."
}
```

### `trailing_audio` (clip-level on sentence)

Use for very short trailing micro-pieces at the end of a track.

```json
{
  "sentence": {
    "start": 102.264,
    "end": 111.499,
    "piece_ids": [50, 51, 52, 53, 54],
    "flags": ["trailing_audio"]
  },
  "note": "Pieces 53-54 are very short trailing content ('だ' + empty)."
}
```

## Invariants

1. **Piece ID uniqueness**: Every piece ID from 0 to N-1 must appear in exactly one clip's `piece_ids` list across the entire mapping array. **Exception**: when `bridge_split` is used (either inter-entry bridge or word+sentence fused in one piece), the same piece_id appears in two adjacent clips — this is the only allowed duplication.
2. **Contiguous indices**: In `unit-sequential` mode, entry indices must be contiguous starting from `current_track_start_index`.
3. **Non-overlapping clips**: Clip time ranges within an entry must not overlap (word end <= sentence start).
4. **Order**: Entries must be in ascending index order. Within each entry, word comes before sentence temporally.

## Bridge split example

When piece 5 contains "...終わった。次の..." where "終わった" belongs to entry A's sentence and "次の" belongs to entry B's word:

```json
{
  "index": 41,
  "word": { "start": 8.0, "end": 9.0, "piece_ids": [4], "flags": [] },
  "sentence": {
    "start": 9.5,
    "end": 11.234,
    "piece_ids": [5],
    "flags": ["bridge_split"]
  },
  "note": "Piece 5 split: sentence ends at 11.234 within the piece."
},
{
  "index": 42,
  "word": {
    "start": 11.234,
    "end": 12.5,
    "piece_ids": [5],
    "flags": ["bridge_split"]
  },
  "sentence": { "start": 13.0, "end": 15.0, "piece_ids": [6], "flags": [] },
  "note": "Piece 5 split: word starts at 11.234 within the same piece."
}
```

Note: piece 5 appears in both clips — this is the ONLY case where a piece_id is duplicated. The `bridge_split` flag signals the cutter to use the intra-piece timestamp boundary.
