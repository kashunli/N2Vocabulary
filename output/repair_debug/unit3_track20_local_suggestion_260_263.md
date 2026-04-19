# Local repair suggestion: 20 1-20.mp3

- Review JSON: `output\review_unit3_track_20.json`
- Entries JSON: `output\unit3_entries\entries_20.json`
- Backend: `whisper_cpp_large-v3-turbo`
- Index window: `260-263`
- Piece window: `9-19`
- Silence settings: noise `-32dB` | duration `0.25`
- Total assignment score: `7.733`

## Piece transcripts

- piece 9: `19.319-21.373` `このナイフは切れ味が鈍い。`
- piece 10: `23.189-24.020` `鋭い`
- piece 11: `24.743-26.550` `クマは鋭い爪を持っている。`
- piece 12: `28.344-28.920` `アライ`
- piece 13: `29.728-31.165` `彼は気性が荒い、`
- piece 14: `32.964-33.892` `強引な`
- piece 15: `34.587-37.680` `与党は国会で強引に法案を通した。`
- piece 16: `39.467-40.155` `勝手な`
- piece 17: `40.850-42.004` `勝手な言動は、`
- piece 18: `42.409-43.970` `他の人の迷惑になる`
- piece 19: `45.693-46.449` `強気な`

## Suggested assignments

### 260 鋭い

- current word: pieces `10` | span `23.189-24.020`
- current sentence: pieces `11` | span `24.743-26.550`
- current note: ASR: くまはするどいつめを→熊はするどい爪を

- word: pieces `10-10` | span `23.189-24.020` | score `1.0` | text `鋭い`
- sentence: pieces `11-11` | span `24.743-26.550` | score `1.0` | text `クマは鋭い爪を持っている。`

Top alternatives:

- word alt 1: pieces `14-14` | span `32.964-33.892` | score `0.417` | text `強引な`
- word alt 2: pieces `12-12` | span `28.344-28.920` | score `0.381` | text `アライ`
- sentence alt 1: pieces `11-12` | span `24.743-28.920` | score `0.927` | text `クマは鋭い爪を持っている。アライ`
- sentence alt 2: pieces `10-11` | span `23.189-26.550` | score `0.906` | text `鋭いクマは鋭い爪を持っている。`

### 261 荒い / 粗い

- current word: pieces `12` | span `28.344-28.920`
- current sentence: pieces `13` | span `29.728-31.165`
- current note: ASR: きしょうがあらい→気性が荒い

- word: pieces `12-12` | span `28.344-28.920` | score `1.0` | text `アライ`
- sentence: pieces `13-13` | span `29.728-31.165` | score `0.963` | text `彼は気性が荒い、`

Top alternatives:

- word alt 1: pieces `10-10` | span `23.189-24.020` | score `0.381` | text `鋭い`
- word alt 2: pieces `14-14` | span `32.964-33.892` | score `0.188` | text `強引な`
- sentence alt 1: pieces `12-13` | span `28.344-31.165` | score `0.869` | text `アライ彼は気性が荒い、`
- sentence alt 2: pieces `13-14` | span `29.728-33.892` | score `0.768` | text `彼は気性が荒い、強引な`

### 262 強引な

- current word: pieces `14` | span `32.964-33.892`
- current sentence: pieces `15` | span `34.587-37.680`
- current note: ASR: ゴインナ→強引な, 予統→与党, ゴインニ→強引に

- word: pieces `14-14` | span `32.964-33.892` | score `1.0` | text `強引な`
- sentence: pieces `15-15` | span `34.587-37.680` | score `1.0` | text `与党は国会で強引に法案を通した。`

Top alternatives:

- word alt 1: pieces `10-10` | span `23.189-24.020` | score `0.417` | text `鋭い`
- word alt 2: pieces `16-16` | span `39.467-40.155` | score `0.417` | text `勝手な`
- sentence alt 1: pieces `15-16` | span `34.587-40.155` | score `0.935` | text `与党は国会で強引に法案を通した。勝手な`
- sentence alt 2: pieces `14-15` | span `32.964-37.680` | score `0.92` | text `強引な与党は国会で強引に法案を通した。`

### 263 勝手な

- current word: pieces `16` | span `39.467-40.155`
- current sentence: pieces `17,18` | span `40.850-43.970`
- current note: Sentence split: 勝手な現道→勝手な言動, 名枠→迷惑

- word: pieces `16-16` | span `39.467-40.155` | score `0.81` | text `勝手な`
- sentence: pieces `17-18` | span `40.850-43.970` | score `0.98` | text `勝手な言動は、他の人の迷惑になる`

Top alternatives:

- word alt 1: pieces `19-19` | span `45.693-46.449` | score `0.381` | text `強気な`
- word alt 2: pieces `12-12` | span `28.344-28.920` | score `0.25` | text `アライ`
- sentence alt 1: pieces `16-18` | span `39.467-43.970` | score `0.91` | text `勝手な勝手な言動は、他の人の迷惑になる`
- sentence alt 2: pieces `17-19` | span `40.850-46.449` | score `0.91` | text `勝手な言動は、他の人の迷惑になる強気な`

