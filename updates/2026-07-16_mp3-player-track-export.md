# MP3-player vocabulary-track export

Status: completed

## Goal

Create one portable folder containing flat `N1`, `N2`, and `N3` subfolders.
Every included CD track must have exactly one same-basename `.mp3` and `.lrc`;
no WebVTT or workflow metadata belongs inside the portable folder.

## Naming contract

Use `unit<unit>-cd<disc>-track<sequence>` and number `track<sequence>` from 1
within each unit/disc pair. For example, N1's first content recording,
`Disc1-02`, becomes `unit1-cd1-track1.mp3` and
`unit1-cd1-track1.lrc`.

- Preserve review sections as distinct units: `Unit4.5` becomes `unit4-5`.
- N1 disc numbers come from `Disc1` / `Disc2` filenames.
- N2 disc numbers come from `1-N` / `2-N`; later `Track N` files are CD2.
- N3 units 1-6 are CD1 and units 7-12 are CD2, matching the retained corpus.
- Order tracks by their first vocabulary entry in the authoritative manifest,
  not by filesystem or lexical filename order.

## Plan

1. Read only the validated `output/track_lyrics/<book>/manifest.json` files.
2. Copy immutable source MP3s and their generated LRC views into a staging
   folder using normalized paired filenames.
3. Atomically replace the generated portable folder after the staging build
   succeeds.
4. Validate exact subfolder names, allowed extensions, one-to-one MP3/LRC
   pairing, counts, and SHA-256 agreement with every source file.

## Result

Created `output/mp3_player_vocab_tracks/` with exactly three subfolders and no
files at its root:

- `N1`: 93 MP3/LRC pairs, 143.7 MiB
- `N2`: 89 MP3/LRC pairs, 112.2 MiB
- `N3`: 65 MP3/LRC pairs, 78.8 MiB

The 247 tracks use the normalized naming contract; for example,
`N1/unit1-cd1-track1.mp3` and `N1/unit1-cd1-track1.lrc`. The copy-ready
subfolders contain only `.mp3` and `.lrc` files and have no nested folders.

## Validation

```powershell
python -m unittest discover -s skills/generateTrackLyrics/tests -v
python skills/generateTrackLyrics/scripts/export_mp3_player.py --validate-only
```

Twelve tests passed. The independent export validator accepted all 247 pairs
with zero errors after checking exact folder/file sets, paired basenames,
counts, and SHA-256 equality with the source MP3/LRC files. The audit manifest
is stored outside the portable folder at
`output/mp3_player_vocab_tracks.manifest.json`.
