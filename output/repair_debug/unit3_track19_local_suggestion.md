# Local repair suggestion: 19 1-19.mp3

- Review JSON: `output\review_unit3_track_19.json`
- Entries JSON: `output\unit3_entries\entries_19.json`
- Backend: `whisper_cpp_large-v3-turbo`
- Index window: `253-255`
- Piece window: `22-30`
- Silence settings: noise `-32dB` | duration `0.25`
- Total assignment score: `5.98`

## Piece transcripts

- piece 22: `52.438-55.267` `いつも部下の成果を自分のものにしてしまう。`
- piece 23: `56.995-57.961` `肉らしい`
- piece 24: `58.641-59.942` `我が子は可愛いが`
- piece 25: `60.455-61.891` `反抗的な態度をとると`
- piece 26: `62.361-63.487` `憎らしい時もある。`
- piece 27: `65.223-65.825` `にくい`
- piece 28: `66.542-68.513` `父を殺した犯人が憎い。`
- piece 29: `70.178-70.980` `険しい`
- piece 30: `71.722-73.571` `険しい山道を登る。`

## Suggested assignments

### 253 憎らしい

- current word: pieces `23` | span `56.995-57.961`
- current sentence: pieces `24,25,26` | span `58.641-63.487`
- current note: Recut 2026-04-18 from 0.25s silence pieces: word=23 sentence=24-26; repaired prior merged window.

- word: pieces `23-23` | span `56.995-57.961` | score `1.0` | text `肉らしい`
- sentence: pieces `24-26` | span `58.641-63.487` | score `1.0` | text `我が子は可愛いが反抗的な態度をとると憎らしい時もある。`

Top alternatives:

- word alt 1: pieces `29-29` | span `70.178-70.980` | score `0.583` | text `険しい`
- word alt 2: pieces `27-27` | span `65.223-65.825` | score `0.562` | text `にくい`
- sentence alt 1: pieces `24-27` | span `58.641-65.825` | score `0.964` | text `我が子は可愛いが反抗的な態度をとると憎らしい時もある。にくい`
- sentence alt 2: pieces `23-26` | span `56.995-63.487` | score `0.942` | text `肉らしい我が子は可愛いが反抗的な態度をとると憎らしい時もある。`

### 254 憎い

- current word: pieces `27` | span `65.223-65.825`
- current sentence: pieces `28` | span `66.542-68.513`
- current note: Recut 2026-04-18 from 0.25s silence pieces: word=27 sentence=28; repaired shifted mapping.

- word: pieces `27-27` | span `65.223-65.825` | score `1.0` | text `にくい`
- sentence: pieces `28-28` | span `66.542-68.513` | score `1.0` | text `父を殺した犯人が憎い。`

Top alternatives:

- word alt 1: pieces `23-23` | span `56.995-57.961` | score `0.562` | text `肉らしい`
- word alt 2: pieces `29-29` | span `70.178-70.980` | score `0.381` | text `険しい`
- sentence alt 1: pieces `27-28` | span `65.223-68.513` | score `0.927` | text `にくい父を殺した犯人が憎い。`
- sentence alt 2: pieces `28-29` | span `66.542-70.980` | score `0.906` | text `父を殺した犯人が憎い。険しい`

### 255 険しい

- current word: pieces `29` | span `70.178-70.980`
- current sentence: pieces `30` | span `71.722-73.571`
- current note: Recut 2026-04-18 from 0.25s silence pieces: word=29 sentence=30; split former merged word+sentence clip.

- word: pieces `29-29` | span `70.178-70.980` | score `1.0` | text `険しい`
- sentence: pieces `30-30` | span `71.722-73.571` | score `1.0` | text `険しい山道を登る。`

Top alternatives:

- word alt 1: pieces `23-23` | span `56.995-57.961` | score `0.583` | text `肉らしい`
- word alt 2: pieces `27-27` | span `65.223-65.825` | score `0.381` | text `にくい`
- sentence alt 1: pieces `29-30` | span `70.178-73.571` | score `0.851` | text `険しい険しい山道を登る。`
- sentence alt 2: pieces `28-30` | span `66.542-73.571` | score `0.48` | text `父を殺した犯人が憎い。険しい険しい山道を登る。`

