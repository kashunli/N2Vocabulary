# Local repair suggestion: 17 1-17.mp3

- Review JSON: `output\review_unit3_track_17.json`
- Entries JSON: `output\unit3_entries\entries_17.json`
- Backend: `whisper_cpp_large-v3-turbo`
- Index window: `230-231`
- Piece window: `24-32`
- Silence settings: noise `-32dB` | duration `0.25`
- Total assignment score: `3.954`

## Piece transcripts

- piece 24: `58.694-59.595` `かわいそうになった。`
- piece 25: `61.342-62.253` `気の毒な`
- piece 26: `63.047-63.561` `彼女を`
- piece 27: `64.070-66.908` `先日、お父さんを事故で亡くされたそうだよ。`
- piece 28: `67.998-69.058` `お気の毒に`
- piece 29: `70.794-71.654` `貧しい`
- piece 30: `72.454-73.051` `私は`
- piece 31: `73.492-74.930` `貧しい家に育った。`
- piece 32: `76.728-77.364` `惜しい`

## Suggested assignments

### 230 気の毒な

- current word: pieces `25` | span `61.342-62.253`
- current sentence: pieces `26,27` | span `63.047-66.908`
- current note: ASR: 木の毒な→気の毒な, 眠れて→恵まれて

- word: pieces `25-25` | span `61.342-62.253` | score `1.0` | text `気の毒な`
- sentence: pieces `26-28` | span `63.047-69.058` | score `0.974` | text `彼女を先日、お父さんを事故で亡くされたそうだよ。お気の毒に`

Top alternatives:

- word alt 1: pieces `28-28` | span `67.998-69.058` | score `0.795` | text `お気の毒に`
- word alt 2: pieces `25-26` | span `61.342-63.561` | score `0.42` | text `気の毒な彼女を`
- sentence alt 1: pieces `27-28` | span `64.070-69.058` | score `0.93` | text `先日、お父さんを事故で亡くされたそうだよ。お気の毒に`
- sentence alt 2: pieces `26-29` | span `63.047-71.654` | score `0.927` | text `彼女を先日、お父さんを事故で亡くされたそうだよ。お気の毒に貧しい`

### 231 貧しい

- current word: pieces `28,29` | span `67.998-71.654`
- current sentence: pieces `30,31` | span `72.454-74.930`
- current note: Word segment merged with next word boundary, ASR: お気の毒にまずしい

- word: pieces `29-29` | span `70.794-71.654` | score `1.0` | text `貧しい`
- sentence: pieces `30-31` | span `72.454-74.930` | score `1.0` | text `私は貧しい家に育った。`

Top alternatives:

- word alt 1: pieces `32-32` | span `76.728-77.364` | score `0.595` | text `惜しい`
- word alt 2: pieces `29-30` | span `70.794-73.051` | score `0.382` | text `貧しい私は`
- sentence alt 1: pieces `30-32` | span `72.454-77.364` | score `0.931` | text `私は貧しい家に育った。惜しい`
- sentence alt 2: pieces `29-31` | span `70.794-74.930` | score `0.911` | text `貧しい私は貧しい家に育った。`

