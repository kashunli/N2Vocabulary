---
name: generate-track-lyrics
description: Generate and validate LRC/WebVTT lyrics for N1, N2, and N3 vocabulary CD tracks from accepted timing ledgers or CD-derived clips.
---

# Generate Track Lyrics

This workflow keeps the original CD audio immutable and generates synchronized
Japanese text beside it.

## Inputs

- N1: `D:\n2Prepare\minikaraWordN1\data\processed\audio_clips\clip_manifest.json`
- N2: live `wordService/data/n2vocab.sqlite`, `audio/`, and `clips/`
- N3: live N3 rows in the same SQLite database plus
  `D:\n2Prepare\N3Words\audio\tracks`

N1's accepted timestamps are authoritative. N2 and N3 timestamps are recovered
by matching decoded clip waveforms against decoded source tracks. ASR is not a
timing authority for this workflow.

## Entrypoint

From the repository root:

```powershell
python skills/generateTrackLyrics/scripts/generate_track_lyrics.py --book n1
python skills/generateTrackLyrics/scripts/generate_track_lyrics.py --book n2
python skills/generateTrackLyrics/scripts/generate_track_lyrics.py --book n3
```

Run all unit tests and validate existing generated manifests:

```powershell
python -m unittest discover skills/generateTrackLyrics/tests -v
python skills/generateTrackLyrics/scripts/validate_track_lyrics.py --book all
```

Build the flat, copy-ready MP3-player folder after the manifests pass:

```powershell
python skills/generateTrackLyrics/scripts/export_mp3_player.py
python skills/generateTrackLyrics/scripts/export_mp3_player.py --validate-only
```

This writes `output/mp3_player_vocab_tracks/{N1,N2,N3}`. Each level folder
contains only same-basename MP3/LRC pairs named
`unit<unit>-cd<disc>-track<sequence>`. The portable folder contains no VTT or
workflow metadata; its audit manifest is stored beside it as
`output/mp3_player_vocab_tracks.manifest.json`.

## Output contract

Each book is written under `output/track_lyrics/<book>/`:

- `manifest.json`: authoritative cue and provenance data
- `validation_report.json`: structural and source-fingerprint checks
- `review_queue.json`: every unresolved or silence-inferred cue
- `tracks/*.lrc`: player-friendly synchronized lyrics
- `tracks/*.vtt`: start/end timed text for browsers and precise review
- `cache/direct_alignments.json` (N3): input-signed resume cache for the
  expensive direct waveform pass

Only `manifest.json` is authoritative. LRC and WebVTT files are generated views.
If canonical text has no distinct utterance on the CD (for example, the track
advances directly to the next verified word), keep it in `unresolved_items`
and the review queue; never invent a timed cue.

## Acceptance

- N1 and N2 may be accepted automatically when every expected cue passes.
- N3 remains `needs_review` while any headword boundary was inferred without a
  surviving CD-derived headword clip.
- Never hide unresolved cues or overwrite source audio.
- Before copying to a player, require the portable-export validator to confirm
  source SHA-256 fingerprints and exact MP3/LRC pairing.
