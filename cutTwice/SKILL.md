---
name: cut-twice
description: Cut a JLPT vocabulary audio track into word-sentence pair clips using silence detection, then split each pair into word and sentence clips with whisper.cpp transcription. No vocabulary content needed -- only the track path, expected pair count, and optional start index. Outputs pairNNN.mp3, wordNNN.mp3, sentenceNNN.mp3, and a pairs.json manifest.
---

# Cut-Twice: Silence-Based Clip Cutter + Transcriber

Pair-first pipeline. No vocabulary content required -- only the track, optional expected pair count, and optional first vocabulary index.

## Folder contract

Keep the skill's file contract explicit:

- **Input track**: read from `audio/...` unless the user gives another path.
- **Durable output**: write pair, word, sentence clips to `clips/<logical-unit-track>/`.
- **Manifest**: keep `pairs.json` beside the clips in the same `clips/<logical-unit-track>/` folder.
- **Review/work artifacts**: if broader audit or mapping files are needed, put them under `work/` in new workflows, or `output/alignment/` while this repository is still in compatibility cleanup.
- **Cache/scratch**: keep Whisper scratch and transcript caches in ignored cache folders, not beside canonical data.

Do not write new finished clips under `output/clips/`; root `clips/` is the current product location.

There are two pair-cutting modes:

- **Strict count mode**: pass `--expected N`; the cutter searches thresholds until it finds exactly `N` pairs.
- **Just-cut mode**: pass `--just-cut`; the cutter uses one default `0.9s` silence pass and keeps whatever pair count it finds. Use this for whole tracks, whole units, or multi-unit exploration when the expected count is unknown.

## Step 1 — Cut by silence

```bash
python cutTwice/cut_by_silence.py \
    --track      "audio/unit1/track01.mp3" \
    --expected   10 \
    [--start-index 1] \
    --output-dir "clips/unit1_track01" \
    [--silence-duration 0.9] \
    [--noise-db -35] \
    [--dry-run]
```

For unknown pair counts:

```bash
python cutTwice/cut_by_silence.py \
    --track      "audio/unit1/full_unit.mp3" \
    --just-cut \
    --start-index 1 \
    --output-dir "clips/unit1_auto"
```

**What it does:**
1. Runs ffmpeg `silencedetect` with `noise=<noise-db>dB:d=<silence-duration>`.
2. Derives non-silent pieces from the silence intervals.
3. If piece count ≠ expected, adjusts threshold and retries (searches 0.2s–3.0s range).
4. Cuts each piece to `<output-dir>/pairNNN.mp3`, starting from `--start-index`.
5. Writes `<output-dir>/pairs.json` with `mode`, `expected_pairs`, `expected_range`, `detected_pairs`, `silence_intervals`, and per-pair `index`, `start`, `end`, `duration`, `clip_path`, `transcription: null`.

**Key parameters:**

| Flag | Default | Notes |
|------|---------|-------|
| `--start-index` | 1 | First filename/index number. Use vocabulary number starts like `--start-index 628` when track numbering should match word IDs |
| `--just-cut` | off | Do not require `--expected`; use one `0.9s` silence pass and keep all detected pairs |
| `--silence-duration` | 0.9s | Starting threshold; auto-adjusted if piece count is wrong |
| `--noise-db` | -35 | Lower (e.g. -40) for noisy audio; raise for clean studio |
| `--dry-run` | off | Report detected pieces without cutting files |

**Outputs:**
- `clips/unitX_trackYY/pairNNN.mp3` ... starting at `--start-index`
- `clips/unitX_trackYY/pairs.json`

Use one output folder per logical source track. The folder name should be stable enough to reference from `vocabulary.json`, for example `clips/unit7_track47` or `clips/unit7_5_track03`.

## Step 2 — Transcribe pairs for review

In just-cut mode, transcribe whole pairs before splitting words. Review whether each `pairNNN.mp3` contains exactly one word plus one sentence that contains that word. If the pair transcript looks reasonable, continue to word/sentence splitting. If not, keep the manifest: the timestamps and silence intervals make later manual repair easier.

```bash
python cutTwice/transcribe_pairs.py \
    --pairs-json  "clips/unit1_auto/pairs.json" \
    --wcpp-binary "tools/whispercpp-windows/whisper-cli.exe" \
    --wcpp-model  "tools/whispercpp-windows/ggml-large-v3-turbo.bin" \
    [--language ja] \
    [--overwrite]
```

`transcribe_pairs.py` records `transcription_error` when one pair fails and continues through the rest of the manifest.

## Step 3 — Split each pair into word + sentence

```bash
python cutTwice/cut_word.py \
    --pairs-json  "clips/unit1_track01/pairs.json" \
    --wcpp-binary "tools/whispercpp-windows/whisper-cli.exe" \
    --wcpp-model  "tools/whispercpp-windows/ggml-large-v3-turbo.bin" \
    [--language ja] \
    [--silence-duration 0.5] \
    [--noise-db -35] \
    [--pad 0.15] \
    [--overwrite]
```

**What it does:**
1. Reads `pairs.json`.
2. Runs silence detection inside each `pairNNN.mp3`.
3. Cuts first speech span to `wordNNN.mp3`.
4. Cuts the remaining speech span(s) to `sentenceNNN.mp3`.
5. Transcribes both clips with whisper.cpp (`-ml 1 -oj -nt`).
6. Writes word/sentence paths, cut times, split speech pieces, and transcriptions back into `pairs.json`.

Skips pairs that already have word/sentence paths unless `--overwrite` is passed.
If a pair cannot be split or transcribed, `cut_word.py` records `split_error`, `word_transcription_error`, or `sentence_transcription_error` and keeps going. Do not stop a whole-unit run because one word has an error.

## Optional — Transcribe whole pairs only

This is the same command used in Step 2. Use it without `cut_word.py` when you only want pair-level review.

```bash
python cutTwice/transcribe_pairs.py \
    --pairs-json  "clips/unit1_track01/pairs.json" \
    --wcpp-binary "tools/whispercpp-windows/whisper-cli.exe" \
    --wcpp-model  "tools/whispercpp-windows/ggml-large-v3-turbo.bin" \
    [--language ja] \
    [--overwrite]
```

**Environment variable shortcuts:**
```bash
export WHISPER_CPP_BIN=tools/whispercpp-windows/whisper-cli.exe
export WHISPER_CPP_MODEL=tools/whispercpp-windows/ggml-large-v3-turbo.bin
```

## pairs.json structure

```json
{
  "track": "audio/unit1/track01.mp3",
  "mode": "strict_count",
  "expected_pairs": 10,
  "expected_range": {"start": 1, "end": 10},
  "detected_pairs": 10,
  "silence_duration_used": 1.1,
  "noise_db": -35.0,
  "total_duration": 142.5,
  "silence_intervals": [
    {"start": 4.201, "end": 5.712}
  ],
  "pairs": [
    {
      "index": 1,
      "start": 0.512,
      "end": 4.201,
      "duration": 3.689,
      "clip_path": "unit1_track01/pair001.mp3",
      "transcription": null,
      "word_start": 0.0,
      "word_end": 1.2,
      "word_split_threshold_used": 0.5,
      "word_path": "unit1_track01/word001.mp3",
      "word_transcription": "おそらく",
      "sentence_start": 1.5,
      "sentence_end": 4.201,
      "sentence_path": "unit1_track01/sentence001.mp3",
      "sentence_transcription": "おそらく、彼は来ないでしょう。"
    }
  ]
}
```

## Typical workflow

```bash
# 1. Dry run first to inspect piece detection
python cutTwice/cut_by_silence.py \
    --track audio/unit1/track01.mp3 \
    --expected 10 \
    --start-index 1 \
    --output-dir clips/unit1_track01 \
    --dry-run

# 2. Cut for real
python cutTwice/cut_by_silence.py \
    --track audio/unit1/track01.mp3 \
    --expected 10 \
    --start-index 1 \
    --output-dir clips/unit1_track01

# 3. Split each pair into word/sentence clips and transcribe them
python cutTwice/cut_word.py \
    --pairs-json clips/unit1_track01/pairs.json \
    --wcpp-binary tools/whispercpp-windows/whisper-cli.exe \
    --wcpp-model tools/whispercpp-windows/ggml-large-v3-turbo.bin \
    --overwrite
```

## Unit7 名詞C example

Track filenames in `audio/Unit7 名詞C` do not exactly match the logical track numbers, so use this mapping:

```bash
# track47: words 628-630, 3 pairs
python cutTwice/cut_by_silence.py --track "audio/Unit7 名詞C/47 1-47.mp3" --expected 3 --start-index 628 --output-dir "clips/unit7_track47"
python cutTwice/cut_word.py --pairs-json "clips/unit7_track47/pairs.json" --wcpp-binary "tools/whispercpp-windows/whisper-cli.exe" --wcpp-model "tools/whispercpp-windows/ggml-large-v3-turbo.bin" --overwrite

# track48: words 631-647, 17 pairs
python cutTwice/cut_by_silence.py --track "audio/Unit7 名詞C/48 2-1.mp3" --expected 17 --start-index 631 --output-dir "clips/unit7_track48"
python cutTwice/cut_word.py --pairs-json "clips/unit7_track48/pairs.json" --wcpp-binary "tools/whispercpp-windows/whisper-cli.exe" --wcpp-model "tools/whispercpp-windows/ggml-large-v3-turbo.bin" --overwrite

# track49: words 648-655, 8 pairs
python cutTwice/cut_by_silence.py --track "audio/Unit7 名詞C/49 2-2.mp3" --expected 8 --start-index 648 --output-dir "clips/unit7_track49"
python cutTwice/cut_word.py --pairs-json "clips/unit7_track49/pairs.json" --wcpp-binary "tools/whispercpp-windows/whisper-cli.exe" --wcpp-model "tools/whispercpp-windows/ggml-large-v3-turbo.bin" --overwrite
```

## Unit7.5+ CD2 filename convention

For `Unit7.5 まとめ2同じ漢字を含む名詞`, Unit8, and later CD2 units, treat the leading number in the raw filename as the logical track number after CD2 track02.

Examples:

- `03 Track 3.mp3` -> logical `track03`, output folder `clips/unit7_5_track03`
- `04 Track 4.mp3` -> logical `track04`, output folder `clips/unit7_5_track04`

When the expected pair count is unknown, use just-cut mode first, then transcribe pairs for review, then split words:

```bash
python cutTwice/cut_by_silence.py --track "audio/Unit7.5 まとめ2同じ漢字を含む名詞/03 Track 3.mp3" --just-cut --output-dir "clips/unit7_5_track03"
python cutTwice/transcribe_pairs.py --pairs-json "clips/unit7_5_track03/pairs.json" --wcpp-binary "tools/whispercpp-windows/whisper-cli.exe" --wcpp-model "tools/whispercpp-windows/ggml-large-v3-turbo.bin" --overwrite
python cutTwice/cut_word.py --pairs-json "clips/unit7_5_track03/pairs.json" --wcpp-binary "tools/whispercpp-windows/whisper-cli.exe" --wcpp-model "tools/whispercpp-windows/ggml-large-v3-turbo.bin" --overwrite
```

## Troubleshooting

- **Can't find N pieces**: Try `--noise-db -40` (lower floor catches more silence) or `--noise-db -30` (stricter).
- **Pieces too short / slivers**: Normal — the script ignores pieces < 50ms automatically.
- **Word/sentence split failed**: Check `split_error` in `pairs.json`; the pair may need a manual cut if there is not enough silence between the word and sentence.
- **Transcription blank or garbled**: Clip may be too short, clipped, or silence-heavy. Check clip with `ffplay`; Whisper text is verification aid, not the source of truth.
