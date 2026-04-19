# Unit 4 clip audit

- Review source: `output\review_unit4_all.json`
- Backend: `whisper_cpp_large-v3-turbo`
- Total rows: `185`
- OK: `161`
- ASR noise only: `10`
- Suspect: `14`

## Suspects

### 284 意識スル (22 1-21.mp3)

- Expected sentence: `意識ははっきりしていたが、体が動かなかった。`
- Word: `ご視聴ありがとうございました` | score `0.095` | status `suspect`
- Sentence: `ご視聴ありがとうございました` | score `0.293` | status `suspect`
- Reason(s): word_clip_contains_sentence_audio, word_clip_too_long_or_merged, sentence_asr_mismatch
- Existing note: none

### 293 損 (23 1-22.mp3)

- Expected sentence: `株が下がって損をした。`
- Word: `3` | score `0.0` | status `suspect`
- Sentence: `株が下がって損をした。` | score `1.0` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: none

### 323 一般 (26 1-26.mp3)

- Expected sentence: `これは一般の店では手に入らない薬だ。`
- Word: `パン` | score `0.667` | status `suspect`
- Sentence: `これは一般の店では手に入らない薬だ。` | score `1.0` | status `ok`
- Reason(s): word_orthography_or_reading_drift, word_possible_micro_region_lead_in
- Existing note: none

### 328 きっかけ (26 1-26.mp3)

- Expected sentence: `けんかのきっかけは、つまらないことだった。`
- Word: `かけ` | score `0.667` | status `suspect`
- Sentence: `喧嘩のきっかけはつまらないことだ。` | score `0.947` | status `ok`
- Reason(s): word_orthography_or_reading_drift, word_possible_micro_region_lead_in
- Existing note: none

### 333 延期スル (26 1-26.mp3)

- Expected sentence: `大雨のため、運動会は1週間後に延期された。`
- Word: `大雨のため` | score `0.0` | status `suspect`
- Sentence: `運動会は1週間後に延期された。` | score `0.863` | status `suspect`
- Reason(s): word_clip_contains_sentence_audio, word_matches_neighbor_335, sentence_prefix_or_suffix_only
- Existing note: none

### 341 支持スル (27 1-27.mp3)

- Expected sentence: `私は首相を支持している。`
- Word: `CG` | score `0.0` | status `suspect`
- Sentence: `私は首相を支持している。` | score `1.0` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: none

### 343 当選スル (27 1-27.mp3)

- Expected sentence: `先日の選挙で、知り合いが市長に当選した。`
- Word: `先日の選挙で` | score `0.25` | status `suspect`
- Sentence: `知り合いが市長に当選した` | score `0.744` | status `suspect`
- Reason(s): word_clip_contains_sentence_audio, word_matches_neighbor_350, sentence_prefix_or_suffix_only
- Existing note: none

### 353 実物 (27 1-27.mp3)

- Expected sentence: `このダイヤモンドは、写真で見ると大きく見えるが、実物はもっと小さい。`
- Word: `実物` | score `1.0` | status `ok`
- Sentence: `このダイヤモンドは写真で見ると大きく見えるが、` | score `0.794` | status `suspect`
- Reason(s): sentence_prefix_or_suffix_only
- Existing note: none

### 362 集合スル (28 1-28.mp3)

- Expected sentence: `面接を受ける人は、予定時間の30分前に会場に集合してください`
- Word: `面接を受ける人は、` | score `0.222` | status `suspect`
- Sentence: `予定時間の30分前に会場に集合してください。` | score `0.838` | status `suspect`
- Reason(s): word_clip_contains_sentence_audio, word_matches_neighbor_366, sentence_prefix_or_suffix_only
- Existing note: none

### 368 ／ヲ停止スル (28 1-28.mp3)

- Expected sentence: `そのスーパーは停電のため、営業を停止した。`
- Word: `停止` | score `0.667` | status `suspect`
- Sentence: `そのスー��ーは停電のため営業を停止した。` | score `0.939` | status `ok`
- Reason(s): word_orthography_or_reading_drift, word_possible_micro_region_lead_in
- Existing note: none

### 369 低下スル (28 1-28.mp3)

- Expected sentence: `高く登れば登るほど、気温は低下する。`
- Word: `高く登れば登るほど` | score `0.235` | status `suspect`
- Sentence: `気温は低下する。` | score `0.625` | status `suspect`
- Reason(s): word_clip_contains_sentence_audio, sentence_prefix_or_suffix_only
- Existing note: none

### 370 超過スル (28 1-28.mp3)

- Expected sentence: `彼女の荷物は規定の重量を10キロも超過していた。`
- Word: `彼女の荷物は、` | score `0.133` | status `suspect`
- Sentence: `規定の重量を10キロも超過していた。` | score `0.847` | status `suspect`
- Reason(s): word_clip_contains_sentence_audio, sentence_prefix_or_suffix_only
- Existing note: none

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

