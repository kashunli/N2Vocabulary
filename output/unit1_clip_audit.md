# Unit 1 clip audit

- Review source: `output\review_unit1_combined.json`
- Backend: `whisper_cpp_large-v3-turbo`
- Total rows: `100`
- OK: `81`
- ASR noise only: `12`
- Suspect: `7`

## Suspects

### 11 他人 (02 1-02.mp3)

- Word: `バニー` | score `0.4` | status `suspect`
- Sentence: `友達だと思って声をかけたら、全くの他人だった。` | score `1.0` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: none

### 33 地位 (03 1-03.mp3)

- Word: `G` | score `0.0` | status `suspect`
- Sentence: `Cが上がるとともにストレスも増える。` | score `0.919` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: medium split confirmed; remapped to ffmpeg silence edges

### 49 意志 / 意思 (04 1-04.mp3)

- Word: `一喜` | score `0.4` | status `suspect`
- Sentence: `彼女は意思が固いからきっと目的を達成するだろう。` | score `0.954` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: whisper.cpp large-v3-turbo confirms the full 意志 sentence occupies this window

### 54 券 (05 1-05.mp3)

- Word: `M` | score `0.0` | status `suspect`
- Sentence: `あの店はいつも混んでいて、入るのに整理券が必要だ。` | score `1.0` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: none

### 57 針 (05 1-05.mp3)

- Word: `ハディ` | score `0.4` | status `suspect`
- Sentence: `針に糸を通す。` | score `1.0` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: none

### 58 栓 (05 1-05.mp3)

- Word: `1000` | score `0.0` | status `suspect`
- Sentence: `ビールの線を抜く。` | score `1.0` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: none

### 59 湯気 (05 1-05.mp3)

- Word: `ユングエ` | score `0.333` | status `suspect`
- Sentence: `うどんの湯気で眼鏡が曇ってしまった。` | score `1.0` | status `ok`
- Reason(s): word_asr_mismatch
- Existing note: none

