# Mapping Schema

Use this JSON shape for GPT-produced mapping output.

## Normal case

```json
[
  {
    "index": 214,
    "word": {
      "start": 0.00,
      "end": 1.46,
      "piece_ids": [0]
    },
    "sentence": {
      "start": 1.88,
      "end": 4.94,
      "piece_ids": [1, 2]
    },
    "note": "headword and sentence align cleanly to whole speech pieces"
  }
]
```

## Near-silence snap case

GPT should still output the intended timestamps. The downstream cutter will prefer the nearest real silence edge even if it is slightly outside the nominal tolerance.

```json
[
  {
    "index": 219,
    "word": {
      "start": 31.56,
      "end": 32.64,
      "piece_ids": [11]
    },
    "sentence": {
      "start": 33.32,
      "end": 35.86,
      "piece_ids": [13]
    },
    "note": "sentence start is close to the next real silence edge; no bridge split needed"
  }
]
```

## Bridge-split case

Use this only when one speech piece truly bridges two adjacent items and silence detection failed to separate them.

```json
[
  {
    "index": 300,
    "word": {
      "start": 10.20,
      "end": 10.92,
      "piece_ids": [5],
      "flags": ["bridge_split"],
      "preserve_boundaries": ["end"]
    },
    "sentence": {
      "start": 11.04,
      "end": 13.40,
      "piece_ids": [6, 7]
    },
    "flags": ["needs_local_review"],
    "note": "piece 5 contains the tail of the previous item and the headword onset for this item; preserve the GPT split point on the word end"
  },
  {
    "index": 301,
    "word": {
      "start": 10.92,
      "end": 11.18,
      "piece_ids": [5],
      "flags": ["bridge_split"],
      "preserve_boundaries": ["start"]
    },
    "sentence": {
      "start": 11.60,
      "end": 14.20,
      "piece_ids": [8, 9]
    },
    "note": "same bridge piece shared with the previous item; the shared piece must still be fully accounted for"
  }
]
```

## Required conventions

- Every speech piece in the selected run must appear in at least one `piece_ids` list.
- Prefer assigning a whole piece to one item whenever possible.
- If a piece is shared by adjacent items, mark the affected clip with `bridge_split`.
- Use `preserve_boundaries` only for the boundary that must remain inside a speech piece.
- Supported flags:
  - `bridge_split`
  - `near_silence_snap`
  - `needs_local_review`
