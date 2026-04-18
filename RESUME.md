# Project Resume — N2Vocabulary Audio Repair

Last updated: 2026-04-18

## Where We Are

This repo is now using the **`whisper.cpp` + Vulkan + `ggml-large-v3-turbo`** workflow as the default for repair and audit work on this Windows machine.

Environment:

- GPU: AMD RX 6950 XT
- Backend: `whisper.cpp`
- Binary: `tools/whispercpp-windows/whisper-cli.exe`
- Model: `tools/whispercpp-windows/ggml-large-v3-turbo.bin`
- Default silence pass: `0.25s`
- Local repair silence pass: `0.12s`, then `0.08s` only for suspected micro-regions

The important shift is that we no longer trust one ASR pass or old mapping notes by themselves. The working loop is now:

1. Save full-track transcription caches.
2. Re-transcribe the already-cut clips.
3. Repair only entries that still look structurally wrong.
4. Recut touched tracks.
5. Re-audit the output clips.

## What Changed Today

### Code / workflow changes

- Added `parse/scripts/cache_track_transcripts.py`
  - Saves per-track:
    - raw `whisper.cpp` `-oj -ml 1` JSON
    - normalized `segments.json`
    - flattened transcript text
    - manifest JSON
- Hardened `parse/scripts/align_track_by_llm.py`
  - `whisper.cpp` clip transcription now writes scratch files into `output/whisper_tmp/`
  - This fixes a Windows issue where Python-created temp directories caused `whisper-cli` to return success but create no JSON for short clips
- Updated `parse/scripts/audit_unit_clips.py`
  - If `expected_sentence` is empty but `note` starts with `sentence: ...`, the audit now uses that note text as the expected sentence
  - This removed a false suspect on Unit 2 entry `131`
  - Clip transcript cache keys now include file size + mtime
  - This prevents a recut clip from reusing a stale transcript cache entry at the same path

### Unit 1 status

Unit 1 is in much better shape and the major structural problems were already fixed before today.

Known good outcomes from the previous repair passes:

- `sentence47` fixed
- `word74` fixed
- `word75` fixed
- focused recut/audit on tracks `04` and `06` confirmed the user-reported problems were fixed

Unit 1 is no longer the active blocker.

### Unit 2 status

Unit 2 is **much cleaner now** after a focused recut / re-audit pass.

Facts:

- Review source: `output/review_unit2_all.json`
- Expected row count: `119`
- Index range: `101-220`
- Intentional missing index: `171`

Saved Unit 2 full-track caches:

- `output/whisper_cache/unit2_large_v3_turbo_wcpp_manifest.json`
- `output/whisper_cache/unit2_track_08_large_v3_turbo_wcpp_ml1.json`
- `output/whisper_cache/unit2_track_08_large_v3_turbo_wcpp_segments.json`
- `output/whisper_cache/unit2_track_08_large_v3_turbo_wcpp_transcript.txt`
- same pattern saved for tracks `09` through `16`

Saved Unit 2 full clip audit:

- `output/unit2_clip_audit.json`
- `output/unit2_clip_audit_suspect.json`
- `output/unit2_clip_audit.md`
- `output/unit02_clip_transcript_cache_whisper_cpp_large-v3-turbo_post_recut.json`

Current full Unit 2 audit result:

- `119` rows
- `106 ok`
- `6 asr_noise`
- `7 suspect`

## Unit 2: What The Audit Actually Means

The original plan assumed tracks `11` and `12` would be the first repair wave because their mapping notes looked scary. The new large-backend audit changed that:

- Tracks `11` and `12` do **not** currently show real structural clip defects
- They have ugly historical notes, but the actual cut clips are presently acceptable
- They should **not** be touched next unless a later audit proves otherwise

The recut wave on tracks `13`, `14`, and `16` is now done.

Confirmed good after recut + fresh audit cache:

- Track `13`
  - `174`
  - `181`
- Track `16`
  - `214`
  - `216`
- Track `13`
  - `177`

These were false holdovers from a stale clip transcript cache, not surviving structural defects.

### Remaining backlog

- Track `09`
  - `118`
  - `125`
  - `128`
- Track `10`
  - `134`
  - `146`
- Track `13`
- Track `15`
  - `210`
- Track `14`
  - `193`

Current read on these:

- `118`, `134`, `210` look like short-word ASR misses
- `146` is a very short word clip and likely ASR noise
- `125` and `128` currently look more like ambiguous word-ASR than confirmed boundary leaks
- `193` is the only Unit 2 item that still deserves human caution after the recut wave
  - full-track cache still shows a clean local headword region around `38.64-39.59`
  - sentence onset is still around `39.90`
  - isolated clip ASR keeps hallucinating on the word clip even when locally tightened
  - treat it as an unresolved verification outlier unless ear-checking or another backend proves a real boundary defect

### One special metadata case already handled

- `131` was a false suspect because the sentence lived only in `note`
- The audit script now handles this case properly

## Important Evidence From Today

### Recut was necessary, but the first re-audit was still misleading

The first post-recut Unit 2 audit still reported `174`, `181`, `214`, and `216` as merged.

That result was wrong because the clip transcript cache was keyed only by clip path, so the fresh recut clips reused stale transcripts from the older wider cuts.

After re-running with a fresh cache:

- `174` cleared
- `181` cleared
- `214` cleared
- `216` cleared

### Track 14 / entry 193 is still the only notable outlier

Large track cache around the region shows:

- the spoken headword `ふるえる` is around `38.64-39.59`
- the sentence begins around `39.90`
- the recut word clip remains difficult for isolated ASR, even when locally tightened
- this currently looks more like a clip-level ASR hallucination than a confirmed boundary leak

## Kick Start Next Session

Start exactly here:

### 1. If you re-audit after any future recut, use a fresh cache file or rely on the new cache-key behavior

Recommended:

- keep `parse/scripts/audit_unit_clips.py` as-is so file identity is part of the cache key
- if you want a clean artifact trail anyway, pass a new `--cache-json` path after a recut

### 2. If you revisit 193, inspect the local `38.5-44.1` window on `audio/Unit2 動詞A/14 1-14.mp3`

- `output/whisper_cache/unit2_track_14_large_v3_turbo_wcpp_segments.json`
- local silence boundaries from `0.25`, then `0.12`, then `0.08` only if needed
- trust the full-track cache more than the isolated word-clip ASR if they disagree again

### 3. Otherwise, the next useful Unit 2 work is the low-priority backlog

Focus on:

- `118`
- `125`
- `128`
- `134`
- `146`
- `210`

These do **not** currently look like the same kind of structural break that the stale `174/181/214/216` group had.

### 4. If Unit 2 is good enough for now, move on to the next unit and keep the docs aligned

Already updated:

- `jlpt-audio-cutter/SKILL.md`
- this `RESUME.md`

## Commands To Reuse

### Save full-track caches

```bash
python parse/scripts/cache_track_transcripts.py \
  --review-json output/review_unit2_all.json \
  --unit 2 \
  --backend whisper_cpp \
  --wcpp-binary tools/whispercpp-windows/whisper-cli.exe \
  --wcpp-model tools/whispercpp-windows/ggml-large-v3-turbo.bin
```

### Full Unit 2 clip audit

```bash
python parse/scripts/audit_unit_clips.py \
  --backend whisper_cpp \
  --wcpp-binary tools/whispercpp-windows/whisper-cli.exe \
  --wcpp-model tools/whispercpp-windows/ggml-large-v3-turbo.bin \
  --review-json output/review_unit2_all.json \
  --output-json output/unit2_clip_audit.json \
  --suspect-json output/unit2_clip_audit_suspect.json \
  --output-md output/unit2_clip_audit.md \
  --unit 2
```

## Do Not Forget

- Use `python` on this machine
- Prefer `whisper.cpp` large over Python Whisper for repair decisions
- Save caches before changing mappings
- Recut from current mapping before assuming a mapping is still wrong
- Treat Unit 2 tracks `11` and `12` as **currently okay**
- Treat Unit 2 indices `174`, `181`, `193`, `214`, `216` as the next concrete repair targets
- Treat Unit 2 index `171` as intentionally missing, not a data integrity problem
