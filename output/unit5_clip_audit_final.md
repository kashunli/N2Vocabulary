# Unit 5 clip audit

- Review source: `output\review_unit5_synthetic_corrected_resolved.json`
- Backend: `whisper_cpp_large-v3-turbo`
- Total rows: `50`
- OK: `38`
- ASR noise only: `2`
- Suspect: `10`

## Suspects

### 479 サンプル (35 1-35.mp3)

- Expected sentence: `食堂の入り口に料理のサンプルが置いてある。`
- Word: `繧ｵ繝ｳ繝励Ν` | score `0.0` | status `suspect`
- Sentence: `食堂の入り口に料理のサン��ルが置いてある。` | score `0.945` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: none

### 483 オーバー (35 1-35.mp3)

- Expected sentence: `志願者が定員をオーバーした。`
- Word: `オー��ー` | score `0.4` | status `suspect`
- Sentence: `志願者が店員をオー��ーした` | score `0.812` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: none

### 485 カーブ (36 1-36.mp3)

- Expected sentence: `道が大きくカーブしている。`
- Word: `ハー��` | score `0.0` | status `suspect`
- Sentence: `道が大きくカー��している。` | score `0.897` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: none

### 489 トップ (36 1-36.mp3)

- Expected sentence: `100メートル走でトップでゴールインした。`
- Word: `ご視聴ありがとうございました` | score `0.105` | status `suspect`
- Sentence: `100メートル走でトップでゴールインした。` | score `1.0` | status `ok`
- Reason(s): word_clip_too_long_or_merged
- Existing note: none

### 493 レギュラー (36 1-36.mp3)

- Expected sentence: `チームのレギュラーになれるようにがんばっている。`
- Word: `でゆら` | score `0.286` | status `suspect`
- Sentence: `チームのレギュラーになれるように頑張っている` | score `0.977` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: none

### 494 コーチ (36 1-36.mp3)

- Expected sentence: `ここの柔道部のコーチは厳しいことで有名だ。`
- Word: `コー��` | score `0.333` | status `suspect`
- Sentence: `ここの柔道部のコー��は厳しいことで有名だ。` | score `0.926` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: none

### 497 キャンパス (37 1-37.mp3)

- Expected sentence: `この大学のキャンパスは緑が豊かだ。`
- Word: `繧ｭ繝｣繝ｳ繝代せ` | score `0.0` | status `suspect`
- Sentence: `この大学のキャン��スは緑が豊かだ。` | score `0.933` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: none

### 508 サービス (37 1-37.mp3)

- Expected sentence: `当社はお客様に喜ばれるサービスを心がけております`
- Word: `サー��ス当社は` | score `0.333` | status `suspect`
- Sentence: `当社はお客様に喜ばれるサー��スを心がけております` | score `0.954` | status `ok`
- Reason(s): word_clip_too_long_or_merged
- Existing note: none

### 509 アルコール (38 1-38.mp3)

- Expected sentence: `注射の前にアルコールで消毒する。`
- Word: `アルコール注射の前に` | score `0.471` | status `suspect`
- Sentence: `前にアルコールで消毒するデコレーション12月になると多くの店が` | score `0.517` | status `suspect`
- Reason(s): word_clip_too_long_or_merged, sentence_asr_mismatch
- Existing note: none

### 510 デコレーション (38 1-38.mp3)

- Expected sentence: `12月になると、多くの店がクリスマスのデコレーションをする。`
- Word: `クリスマスのデコレーションをする。` | score `0.545` | status `suspect`
- Sentence: `` | score `0.0` | status `suspect`
- Reason(s): word_clip_contains_sentence_audio, word_clip_too_long_or_merged, sentence_transcript_empty
- Existing note: none

