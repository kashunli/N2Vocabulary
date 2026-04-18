# Unit 2 clip audit

- Review source: `output\review_unit2_track_09.json`
- Backend: `whisper_cpp_large-v3-turbo`
- Total rows: `16`
- OK: `13`
- ASR noise only: `2`
- Suspect: `1`

## Suspects

### 128 放る (09 1-09.mp3)

- Word: `オール` | score `0.4` | status `suspect`
- Sentence: `ボールを放る` | score `0.923` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: none

