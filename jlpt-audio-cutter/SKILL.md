---
name: jlpt-audio-cutter
description: Cut, audit, and repair JLPT vocabulary audio clips from training tracks. Use when the user asks to extract, align, verify, or fix word/sentence clips, especially when mismatches cascade across a track or when short Japanese word clips lose leading or trailing moras.
---

# JLPT Audio Cutter

Cut and repair Japanese `word -> sentence` clips with a conservative audit loop. On this machine, prefer `whisper.cpp` with Vulkan on the AMD RX 6900/6950 XT and `ggml-large-v3-turbo.bin` for both repair and audit confirmation.

## Defaults

- Backend: `whisper.cpp`
- GPU: Vulkan on the RX 6900/6950 XT
- Model: `tools/whispercpp-windows/ggml-large-v3-turbo.bin`
- First-pass silence detection: `0.25s`
- Local repair silence detection: `0.12s`, then `0.08s` only when a short leading or trailing mora may have been split off

## Quick Reference

### Backend smoke test
```bash
python parse/scripts/align_track_by_llm.py \
  --backend whisper_cpp \
  --wcpp-binary tools/whispercpp-windows/whisper-cli.exe \
  --wcpp-model tools/whispercpp-windows/ggml-large-v3-turbo.bin \
  --backend-info
```

### Full-track transcription prompt build
```bash
python parse/scripts/align_track_by_llm.py \
  --backend whisper_cpp \
  --wcpp-binary tools/whispercpp-windows/whisper-cli.exe \
  --wcpp-model tools/whispercpp-windows/ggml-large-v3-turbo.bin \
  --track "audio/Unit1 名詞A/05 1-05.mp3" \
  --entries-json output/unit1_entries/entries_05.json \
  --prompt-only
```

### Cut-clip audit with the GPU backend
```bash
python parse/scripts/audit_unit_clips.py \
  --backend whisper_cpp \
  --wcpp-binary tools/whispercpp-windows/whisper-cli.exe \
  --wcpp-model tools/whispercpp-windows/ggml-large-v3-turbo.bin \
  --review-json output/review_unit1_combined.json \
  --output-json output/unit1_clip_audit.json \
  --suspect-json output/unit1_clip_audit_suspect.json \
  --output-md output/unit1_clip_audit.md
```

If you just re-cut clips and want a fresh audit artifact trail, add `--cache-json` with a new filename.

## Recommended Repair Circuit

### 1. Track transcription pass

- Save per-track `whisper.cpp` large caches before editing any mapping.
- Keep both:
  - simplified segment JSON for analysis
  - flattened transcript text for quick inspection
- Use fine-grained output so local boundary analysis is possible.
  - The working `whisper.cpp` call shape is `-oj -ml 1 -l ja`

Expected cache pattern:

- `output/whisper_cache/unit1_track_05_large_v3_turbo_wcpp_segments.json`
- `output/whisper_cache/unit1_track_05_large_v3_turbo_wcpp_transcript.txt`

### 2. Suspect detection pass

- Re-transcribe the final cut clips and compare them against the expected reading and sentence.
- Do not trust one ASR score alone.
- A sentence can still be wrong even when similarity looks decent.
  - Prefix-only clips can score above a naive `0.72` threshold and still be truncated.
- Separate:
  - true boundary failures
  - short-word ASR noise
  - OCR-reading problems

### 3. Local repair pass

- Start from the track-level cache and the current mapping window.
- Inspect local speech regions around the suspect entry with:
  - `0.25s` silence first
  - `0.12s` local silence next
  - `0.08s` only when a micro-region may contain a dropped lead-in or closure
- Re-transcribe individual local regions with `whisper.cpp` large.
- Rebuild the clip from region evidence, not from the old mapping note alone.
- After each repair:
  - re-cut the clip
  - re-audit it
  - only then move on
- Do not trust an old clip transcript cache after a recut.
  - `audit_unit_clips.py` now keys cache entries by file identity, but using a fresh `--cache-json` is still a clean habit when you want a clearly separated post-recut audit.

## Silence Strategy

### First pass: `0.25s`

Use `0.25s` for normal Japanese track alignment.

Why:

- it usually preserves `った / って` closures inside the same spoken region
- it avoids over-splitting normal word-plus-sentence flow
- it works well for track-wide alignment and clip cutting

### Local repair: `0.12s` then `0.08s`

Use shorter local thresholds only in suspect windows.

Why:

- some short headwords lose a tiny lead-in region at `0.25s`
- some sentence tails or clipped closures hide in very short neighboring regions
- over-splitting the whole track is noisy, but over-splitting a small repair window is useful

## Failure Patterns To Check

### Prefix-only sentence clips

Symptom:

- the clip contains only the first half of the sentence
- ASR similarity can still look acceptable

Example:

- `期待していたが` passed audit even though the tail `期待はずれの結果に終わった` was missing

Check:

- compare transcript coverage against both the expected prefix and suffix
- if the clip matches only one edge of the sentence, treat it as truncated

### Short leading mora dropped from word clip

Symptom:

- expected word starts with a short lead-in like `にっ`
- the saved word clip contains only the trailing core, such as `ちゅう`

Examples:

- `日中`
- `日程`

Cause:

- the leading mora sits in a tiny preceding speech region that was excluded by the original boundary

Check:

- inspect the immediately preceding micro-region at `0.12s` or `0.08s`
- test the union of that micro-region with the current word clip

### Final closures and short tails

Symptom:

- the clip sounds correct except the ending is slightly chopped
- often affects `った`, `って`, `き`, `く`, or similar closures

Check:

- verify the tail against neighboring speech regions before widening
- do not widen automatically just because one ASR transcript dropped punctuation or the final mora

### Cascade anchor drift

Symptom:

- one early mapping is wrong
- every later word and sentence shifts forward

Check:

- inspect the whole damaged run as one sequence
- rebuild sequentially from the first confirmed anchor instead of spot-fixing isolated entries

### Short-word ASR noise

Symptom:

- the sentence clip is clearly right
- the word clip transcript is nonsense or a kana/kanji drift

Examples:

- `名簿`, `感情`, `手続き` may be confirmed by `whisper.cpp` large even when a smaller audit model still complains

Rule:

- do not remap short clips on ASR noise alone
- confirm with `whisper.cpp` large, and use manual listening if the large backend and the ear disagree
- if the full-track cache clearly shows the headword region but isolated clip ASR hallucinates, treat that as a verification outlier first, not an automatic boundary failure

## Output Expectations

After a repair pass, keep these artifacts:

- updated mapping JSON
- regenerated review JSON for the touched track
- rebuilt combined review JSON if a unit-level pass was changed
- refreshed clip audit outputs
- track transcription caches under `output/whisper_cache/`
- a focused repair report with:
  - old span
  - new span
  - root cause
  - audit result
  - whether the large backend confirmed the fix

## Practical Rules

- Prefer `whisper.cpp` large over Python Whisper for repair and audit confirmation on this machine.
- Save caches before editing mappings.
- Treat `0.25s` as the default alignment threshold, not the only truth.
- After any recut, make sure the clip audit is not reusing stale path-only cache entries.
- Only widen a clip after confirming that the missing content really lives in the adjacent region.
- Do not “fix” clips like `湯気` or `手続き` from one weak audit transcript alone; confirm with the large backend or manual listening first.
- Keep the repair loop conservative: audit, inspect local regions, repair, re-audit.

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `align_track_by_llm.py` | Full-track transcription, silence inspection, and LLM-guided mapping |
| `audit_unit_clips.py` | Re-audit already-cut clips against expected word and sentence content |
| `recut_contaminated.py` | Re-cut existing mappings when only silence snapping changed |
| `merge_assigned_clips.py` | Merge clip paths into the downstream DB |
