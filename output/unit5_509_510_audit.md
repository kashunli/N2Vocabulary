# Unit 5 clip audit

- Review source: `output\review_unit5_509_510.json`
- Backend: `whisper_cpp_large-v3-turbo`
- Total rows: `2`
- OK: `0`
- ASR noise only: `0`
- Suspect: `2`

## Suspects

### 509 アルコール (38 1-38.mp3)

- Expected sentence: `注射の前にアルコールで消毒する。`
- Word: `アルコール` | score `1.0` | status `ok`
- Sentence: `前にアルコールで消毒するデコレーション12月になると多くの店が` | score `0.517` | status `suspect`
- Reason(s): sentence_asr_mismatch
- Existing note: none

### 510 デコレーション (38 1-38.mp3)

- Expected sentence: `12月になると、多くの店がクリスマスのデコレーションをする。`
- Word: `クリスマスのデコレーションをする。` | score `0.545` | status `suspect`
- Sentence: `` | score `0.0` | status `suspect`
- Reason(s): word_clip_contains_sentence_audio, word_clip_too_long_or_merged, sentence_transcript_empty
- Existing note: none

