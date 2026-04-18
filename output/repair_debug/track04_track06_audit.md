# Unit 1 clip audit

- Review source: `output\repair_debug\review_unit1_track04_track06_subset.json`
- Backend: `whisper_cpp_large-v3-turbo`
- Total rows: `30`
- OK: `26`
- ASR noise only: `2`
- Suspect: `2`

## Suspects

### 49 意志 / 意思 (04 1-04.mp3)

- Word: `一喜` | score `0.4` | status `suspect`
- Sentence: `彼女は意思が固いからきっと目的を達成するだろう。` | score `0.954` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: whisper.cpp large-v3-turbo confirms the full 意志 sentence occupies this window

### 79 現在 (06 1-06.mp3)

- Word: `ご視聴ありがとうございました` | score `0.2` | status `suspect`
- Sentence: `駅前は昔は畑だったが、現在は大きなショッピングセンターになっている。` | score `1.0` | status `ok`
- Reason(s): word_clip_too_long_or_merged
- Existing note: none

