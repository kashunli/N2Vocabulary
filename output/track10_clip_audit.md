# Unit 2 clip audit

- Review source: `output\review_unit2_track_10.json`
- Backend: `whisper_cpp_large-v3-turbo`
- Total rows: `17`
- OK: `15`
- ASR noise only: `1`
- Suspect: `1`

## Suspects

### 134 突く (10 1-10.mp3)

- Word: `救う` | score `0.4` | status `suspect`
- Sentence: `ケンカして相手の胸を手でついた。` | score `1.0` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: ASR: 憲化→けんか

