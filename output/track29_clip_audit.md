# Unit 4 clip audit

- Review source: `output\review_unit4_track_29.json`
- Backend: `whisper_cpp_large-v3-turbo`
- Total rows: `21`
- OK: `18`
- ASR noise only: `1`
- Suspect: `2`

## Suspects

### 375 燃え上がる (29 1-29.mp3)

- Expected sentence: `｛火／闘志／恋心 …｝が燃え上がる。`
- Word: `燃え上がる` | score `1.0` | status `ok`
- Sentence: `火が燃え上がる` | score `0.609` | status `suspect`
- Reason(s): sentence_clip_contains_only_word
- Existing note: none

### 381 干上がる (29 1-29.mp3)

- Expected sentence: `｛池／湖／川 …｝が干上がる。`
- Word: `きあがる` | score `0.75` | status `suspect`
- Sentence: `池が干上がる。` | score `0.842` | status `ok`
- Reason(s): word_matches_neighbor_377
- Existing note: none

