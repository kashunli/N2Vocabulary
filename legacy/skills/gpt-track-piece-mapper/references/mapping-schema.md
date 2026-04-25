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
The preserved boundary may sit inside a piece, but final clip spans should still be non-overlapping and each `piece_id` should still appear only once in the whole JSON array.

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
    "note": "piece 5 needs an exact internal cut point at 10.92; keep the final clips non-overlapping and do not reuse piece id 5 elsewhere"
  }
]
```

## Required conventions

- Every speech piece in the selected run must appear in exactly one `piece_ids` list.
- Final clip spans should not overlap.
- Prefer assigning a whole piece to one item whenever possible.
- If a boundary must stay inside a piece, mark the affected clip with `bridge_split`, but do not duplicate the `piece_id` across adjacent clips.
- Use `preserve_boundaries` only for the boundary that must remain inside a speech piece.
- Supported flags:
  - `bridge_split`
  - `near_silence_snap`
  - `needs_local_review`
