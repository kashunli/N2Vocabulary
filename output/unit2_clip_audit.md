# Unit 2 clip audit

- Review source: `output\review_unit2_all.json`
- Backend: `whisper_cpp_large-v3-turbo`
- Total rows: `119`
- OK: `106`
- ASR noise only: `6`
- Suspect: `7`

## Suspects

### 118 どく (09 1-09.mp3)

- Word: `6.` | score `0.0` | status `suspect`
- Sentence: `ちょっとそこをどいてください。` | score `0.966` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: ASR: ドイテクださい→どいてください

### 125 敷く (09 1-09.mp3)

- Word: `四九` | score `0.0` | status `suspect`
- Sentence: `床に布団を敷く` | score `0.947` | status `ok`
- Reason(s): word_clip_contains_sentence_audio, word_matches_neighbor_123
- Existing note: none

### 128 放る (09 1-09.mp3)

- Word: `ホール` | score `0.8` | status `suspect`
- Sentence: `ボールを放る` | score `0.923` | status `ok`
- Reason(s): word_matches_neighbor_129
- Existing note: none

### 134 突く (10 1-10.mp3)

- Word: `救う` | score `0.4` | status `suspect`
- Sentence: `ケンカして相手の胸を手でついた` | score `0.971` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: ASR: 憲化→けんか

### 146 吐く (10 1-10.mp3)

- Word: `白` | score `0.0` | status `suspect`
- Sentence: `息を吸って吐く。` | score `1.0` | status `ok`
- Reason(s): word_matches_neighbor_139
- Existing note: ASR: 白→はく, word very short

### 193 震える (14 1-14.mp3)

- Word: `ご視聴ありがとうございました` | score `0.0` | status `suspect`
- Sentence: `ふるえるさむさにてあしがぶるぶるふるえた` | score `0.842` | status `ok`
- Reason(s): word_clip_contains_sentence_audio, word_matches_neighbor_190, word_clip_too_long_or_merged
- Existing note: ASR: 震える→ふるえる, split from same segment as 192

### 210 立つ(発つ) (15 1-15.mp3)

- Word: `パッツ` | score `0.4` | status `suspect`
- Sentence: `8月末に海外赴任でヨー��ッパへ立つ予定だ` | score `0.923` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: ASR: パツ→立つ, 不任→赴任

