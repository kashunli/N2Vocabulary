# Unit 5 clip audit

- Review source: `output\review_unit5_synthetic.json`
- Backend: `whisper_cpp_large-v3-turbo`
- Total rows: `50`
- OK: `29`
- ASR noise only: `1`
- Suspect: `20`

## Suspects

### 461 アンテナ (34 1-34.mp3)

- Expected sentence: `アンテナの向きのせいかテレビの映りが悪い。`
- Word: `アン��ナ` | score `0.0` | status `suspect`
- Sentence: `アン��ナの向きのせいか、テレビの映りが悪い。` | score `0.936` | status `ok`
- Reason(s): word_clip_contains_sentence_audio, word_matches_neighbor_469
- Existing note: none

### 462 イヤホン (34 1-34.mp3)

- Expected sentence: `電車の中でイヤホンをつけて音楽を聴いている若者が多い。`
- Word: `やほん` | score `0.0` | status `suspect`
- Sentence: `電車の中でイヤホンをつけて音楽を聴いている若者が多い。` | score `1.0` | status `ok`
- Reason(s): word_clip_contains_sentence_audio, word_matches_neighbor_469
- Existing note: none

### 463 サイレン (34 1-34.mp3)

- Expected sentence: `工場でお昼のサイレンが鳴った。`
- Word: `サイレン` | score `0.0` | status `suspect`
- Sentence: `工場でお昼のサイレンが鳴った。` | score `1.0` | status `ok`
- Reason(s): word_clip_contains_sentence_audio, word_matches_neighbor_471
- Existing note: none

### 464 ード (34 1-34.mp3)

- Expected sentence: `アイロンのコードをコンセントにつないだ。`
- Word: `コード` | score `0.0` | status `suspect`
- Sentence: `アイロンのコードをコンセントにつないだ。` | score `1.0` | status `ok`
- Reason(s): word_clip_contains_sentence_audio, word_matches_neighbor_471
- Existing note: none

### 466 ーター (34 1-34.mp3)

- Expected sentence: `メーターを見ると、電気やガスの使用量がわかる。`
- Word: `メーター` | score `0.0` | status `suspect`
- Sentence: `メーターを見ると、電気やガスの使用量がわかる。` | score `1.0` | status `ok`
- Reason(s): word_clip_contains_sentence_audio, word_matches_neighbor_472
- Existing note: none

### 467 ペア (34 1-34.mp3)

- Expected sentence: `男女がペアになってゲームをした。`
- Word: `ヘア` | score `0.0` | status `suspect`
- Sentence: `男女がペアになってゲームをした` | score `0.97` | status `ok`
- Reason(s): word_matches_neighbor_471
- Existing note: none

### 469 アクセント (34 1-34.mp3)

- Expected sentence: `「おかあさん」のアクセントは、「か」の音にある。`
- Word: `アクセントお母さんのアクセントは` | score `0.455` | status `suspect`
- Sentence: `お母さんのアクセントは、かの音にある。` | score `0.9` | status `ok`
- Reason(s): word_clip_too_long_or_merged
- Existing note: none

### 474 イラスト (35 1-35.mp3)

- Expected sentence: `この本はイラストがたくさんあって内容が理解しやすい。`
- Word: `イラスト` | score `1.0` | status `ok`
- Sentence: `この本はイラストがたくさんあって` | score `0.723` | status `suspect`
- Reason(s): sentence_prefix_or_suffix_only
- Existing note: none

### 479 サンプル (35 1-35.mp3)

- Expected sentence: `食堂の入り口に料理のサンプルが置いてある。`
- Word: `繧ｵ繝ｳ繝励Ν` | score `0.0` | status `suspect`
- Sentence: `食堂の入り口に料理のサン��ルが置いてある。` | score `0.945` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: none

### 483 ーバー (36 1-36.mp3)

- Expected sentence: `志願者が定員をオーバーした。`
- Word: `オー��ー` | score `0.4` | status `suspect`
- Sentence: `志願者が店員をオー��ーした` | score `0.812` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: none

### 485 ーブ (36 1-36.mp3)

- Expected sentence: `道が大きくカーブしている。`
- Word: `ハー��` | score `0.0` | status `suspect`
- Sentence: `道が大きくカー��している。` | score `0.897` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: none

### 489 トップ (36 1-36.mp3)

- Expected sentence: `100メートル走でトップでゴールインした。`
- Word: `100メートル走で、` | score `0.167` | status `suspect`
- Sentence: `100メートル走でトップでゴールインした。` | score `1.0` | status `ok`
- Reason(s): word_clip_contains_sentence_audio, word_clip_too_long_or_merged
- Existing note: none

### 493 ー (37 1-37.mp3)

- Expected sentence: `チームのレギュラーになれるようにがんばっている。`
- Word: `でゆら` | score `0.286` | status `suspect`
- Sentence: `チームのレギュラーになれるように頑張っている` | score `0.977` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: none

### 494 ーチ (37 1-37.mp3)

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

### 505 ーズン (37 1-37.mp3)

- Expected sentence: `日本では12月から2月にかけてが受験のシーズンだ。`
- Word: `シーズン` | score `1.0` | status `ok`
- Sentence: `日本では12月から2月にかけてが、` | score `0.8` | status `suspect`
- Reason(s): sentence_prefix_or_suffix_only
- Existing note: none

### 506 ダイヤ (37 1-37.mp3)

- Expected sentence: `事故で列車のダイヤが乱れたが、数時間後に復旧した。`
- Word: `ダイアグラム` | score `0.444` | status `suspect`
- Sentence: `事故で列車のダイヤが乱れたが、数時間後に復旧した。` | score `1.0` | status `ok`
- Reason(s): word_clip_too_long_or_merged
- Existing note: none

### 508 ービス (37 1-37.mp3)

- Expected sentence: `当社はお客様に喜ばれるサービスを心がけております`
- Word: `サー��ス当社は` | score `0.333` | status `suspect`
- Sentence: `当社はお客様に喜ばれるサー��スを心がけております` | score `0.954` | status `ok`
- Reason(s): word_clip_too_long_or_merged
- Existing note: none

### 509 ール (38 1-38.mp3)

- Expected sentence: `注射の前にアルコールで消毒する。`
- Word: `` | score `0.0` | status `suspect`
- Sentence: `` | score `0.0` | status `suspect`
- Reason(s): word_transcript_empty, sentence_transcript_empty
- Existing note: none

### 510 ーション (38 1-38.mp3)

- Expected sentence: `12月になると、多くの店がクリスマスのデコレーションをする。`
- Word: `` | score `0.0` | status `suspect`
- Sentence: `` | score `0.0` | status `suspect`
- Reason(s): word_transcript_empty, sentence_transcript_empty
- Existing note: none

