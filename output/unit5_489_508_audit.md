# Unit 5 clip audit

- Review source: `output\review_unit5_489_508.json`
- Backend: `whisper_cpp_large-v3-turbo`
- Total rows: `2`
- OK: `0`
- ASR noise only: `0`
- Suspect: `2`

## Suspects

### 489 トップ (36 1-36.mp3)

- Expected sentence: `100メートル走でトップでゴールインした。`
- Word: `ご視聴ありがとうございました` | score `0.105` | status `suspect`
- Sentence: `100メートル走でトップでゴールインした。` | score `1.0` | status `ok`
- Reason(s): word_clip_too_long_or_merged
- Existing note: none

### 508 サービス (37 1-37.mp3)

- Expected sentence: `当社はお客様に喜ばれるサービスを心がけております`
- Word: `当社は` | score `0.0` | status `suspect`
- Sentence: `当社はお客様に喜ばれるサー��スを心がけております` | score `0.954` | status `ok`
- Reason(s): word_clip_contains_sentence_audio
- Existing note: none

