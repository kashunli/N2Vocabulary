# Unit 3 clip audit

- Review source: `output\review_unit3_all.json`
- Backend: `whisper_cpp_large-v3-turbo`
- Total rows: `50`
- OK: `46`
- ASR noise only: `3`
- Suspect: `1`

## Suspects

### 231 貧しい (17 1-17.mp3)

- Expected sentence: `私は貧しい家に育った。`
- Word: `お気の毒に。貧しい。` | score `0.5` | status `suspect`
- Sentence: `私は貧しい家に育った。` | score `1.0` | status `ok`
- Reason(s): word_clip_too_long_or_merged
- Existing note: Word segment merged with next word boundary, ASR: お気の毒にまずしい

