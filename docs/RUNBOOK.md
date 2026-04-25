# Runbook

Run commands from the project root unless a command says otherwise.

## Cut Audio With cutTwice

Known count:

```bash
python cutTwice/cut_by_silence.py --track "audio/Unit7 名詞C/47 1-47.mp3" --expected 3 --start-index 628 --output-dir "clips/unit7_track47"
python cutTwice/cut_word.py --pairs-json "clips/unit7_track47/pairs.json" --wcpp-binary "tools/whispercpp-windows/whisper-cli.exe" --wcpp-model "tools/whispercpp-windows/ggml-large-v3-turbo.bin" --overwrite
```

Unknown count:

```bash
python cutTwice/cut_by_silence.py --track "audio/Unit7.5 まとめ2同じ漢字を含む名詞/03 Track 3.mp3" --just-cut --start-index 656 --output-dir "clips/unit7_5_track03"
python cutTwice/transcribe_pairs.py --pairs-json "clips/unit7_5_track03/pairs.json" --wcpp-binary "tools/whispercpp-windows/whisper-cli.exe" --wcpp-model "tools/whispercpp-windows/ggml-large-v3-turbo.bin" --overwrite
python cutTwice/cut_word.py --pairs-json "clips/unit7_5_track03/pairs.json" --wcpp-binary "tools/whispercpp-windows/whisper-cli.exe" --wcpp-model "tools/whispercpp-windows/ggml-large-v3-turbo.bin" --overwrite
```

## Rebuild HTML Words

```bash
python wordsAndExerciseInHtml/build_words.py
```

This reads `vocabulary.json` and `clips/`, then writes under `wordsAndExerciseInHtml/words/`.

## Rebuild HTML Exercises

```bash
python wordsAndExerciseInHtml/build_exercises.py
```

This reads OCR exercise JSON from `json/` and writes under `wordsAndExerciseInHtml/exercises/`.

## Anki Decks

The built decks currently live under `output/` and have also been deployed to `D:\n2Prepare\ankiCardsToBuilt\` in prior runs. The active Anki build scripts live under `makeAnkiCards/scripts/`.

```bash
python makeAnkiCards/scripts/make_anki.py
python makeAnkiCards/scripts/make_anki_listening.py
```

Both commands read `vocabulary.json` and `clips/` by default, then write `output/N2Words.apkg` and `output/N2Words_listening.apkg`.

## Git Checkpoints

Before large cleanup or generation runs:

```bash
git status --short
git add <intentional files>
git commit -m "short factual message"
```

Do not commit Whisper models, source audio, generated clip folders, `.apkg` decks, or caches unless you are intentionally taking a large binary snapshot.
