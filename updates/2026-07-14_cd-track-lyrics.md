# CD track synchronized lyrics

Status: completed

## Goal

Generate auditable, synchronized Japanese lyrics for the original N1, N2, and
N3 vocabulary-book CD tracks. The implementation and generated artifacts live
in this repository; the N1 and N3 repositories are read-only source datasets.

## Plan

1. Use the accepted N1 `segments.csv` / clip manifest directly.
2. Recover N2 clip offsets with normalized waveform correlation. Match the
   longer sentence clip across tracks in the same unit first, then match the
   short headword clip inside the selected track.
3. Recover N3 clip offsets inside its independently known source-track range.
   Match all surviving CD-derived word and sentence clips. Infer missing
   headword boundaries from the reviewed silence structure and keep those
   cues in an explicit review queue.
4. Store one JSON master manifest per book and generate LRC and WebVTT views
   per track from that manifest.
5. Validate counts, track bounds, cue ordering, overlap, direct-match scores,
   source hashes, and output-file agreement before marking a book accepted.

## Pilot gate

Do not scale N2 or N3 until a representative direct-match pilot clearly
separates the correct source track from incorrect candidates. Initial pilot:

- N3 word 2: correlation `0.993`, offset `6.647s`
- N3 sentence 2: correlation `0.962`, offset `8.606s`
- N2 sentence 1: correct-track correlation `0.995`; best wrong track `0.192`

The pilot passed. Full generation may proceed.

## Result

Implemented the self-contained `skills/generateTrackLyrics/` workflow and
generated authoritative manifests plus per-track LRC/WebVTT views under
`output/track_lyrics/`.

- N1: 2,340 cues on 93 tracks; accepted with 0 errors and 0 review cues.
- N2: 2,320 cues on 89 tracks; 0 errors and 24 explicit review cues.
- N3: 1,714 distinct CD utterances on 65 tracks; 0 errors and 89 review
  records. Eleven canonical rows are not distinct CD utterances (shared aliases
  or confirmed absent between verified anchors), so they remain explicit
  unresolved records instead of fake lyric cues.

The full run exposed and fixed two important source contracts: N2 database
units 4/7 include separate CD folders named Unit4.5/Unit7.5, and some N3
replacement study clips describe sentences or words that are not distinct
utterances on the retained CD track. N3's direct waveform pass is resumable
through an input-signed cache.

## Validation

```powershell
python -m unittest discover -s skills/generateTrackLyrics/tests -v
python skills/generateTrackLyrics/scripts/validate_track_lyrics.py --book all
```

The validator rechecks counts, blank text, physical track bounds, cue overlap,
direct-match thresholds, immutable source SHA-256 fingerprints, and exact
LRC/VTT file agreement. Final result: all three books have 0 validation errors;
N2 and N3 remain `needs_review` only because their review queues are nonempty.
