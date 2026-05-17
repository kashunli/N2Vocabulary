# Runbook

Run commands from the project root unless a command says otherwise.

## Cut Audio With cutTwice

Known count:

```bash
python skills/cutTwice/cut_by_silence.py --track "audio/Unit7 名詞C/47 1-47.mp3" --expected 3 --start-index 628 --output-dir "clips/unit7_track47"
python skills/cutTwice/cut_word.py --pairs-json "clips/unit7_track47/pairs.json" --wcpp-binary "tools/whispercpp-windows/whisper-cli.exe" --wcpp-model "tools/whispercpp-windows/ggml-large-v3-turbo.bin" --overwrite
```

Unknown count:

```bash
python skills/cutTwice/cut_by_silence.py --track "audio/Unit7.5 まとめ2同じ漢字を含む名詞/03 Track 3.mp3" --just-cut --start-index 656 --output-dir "clips/unit7_5_track03"
python skills/cutTwice/transcribe_pairs.py --pairs-json "clips/unit7_5_track03/pairs.json" --wcpp-binary "tools/whispercpp-windows/whisper-cli.exe" --wcpp-model "tools/whispercpp-windows/ggml-large-v3-turbo.bin" --overwrite
python skills/cutTwice/cut_word.py --pairs-json "clips/unit7_5_track03/pairs.json" --wcpp-binary "tools/whispercpp-windows/whisper-cli.exe" --wcpp-model "tools/whispercpp-windows/ggml-large-v3-turbo.bin" --overwrite
```

## Study Words Runtime

```bash
python marks_server.py
```

This starts the local SQLite-backed word server at `http://127.0.0.1:8766/`.
It renders word pages from `output/n2vocab.sqlite`, serves audio from `clips/`,
and persists known/flagged card marks back into the same SQLite database.

Useful routes:

```text
http://127.0.0.1:8766/words/index.html
http://127.0.0.1:8766/words/cards/index.html
http://127.0.0.1:8766/words/cards/unit_01.html
http://127.0.0.1:8766/words/by_unit/unit_01.html
```

`wordsAndExerciseInHtml/build_words.py` and
`wordsAndExerciseInHtml/build_word_cards.py` are optional static snapshot
builders. Use them only when you intentionally want generated HTML files.

## Rebuild HTML Exercises

```bash
python wordsAndExerciseInHtml/build_exercises.py
```

This reads OCR exercise JSON from `json/` and writes under `wordsAndExerciseInHtml/exercises/`.

## Anki Decks

The built decks currently live under `output/` and have also been deployed to `D:\n2Prepare\ankiCardsToBuilt\` in prior runs. The active Anki build scripts live under `skills/makeAnkiCards/scripts/`.

```bash
python skills/makeAnkiCards/scripts/make_anki.py
python skills/makeAnkiCards/scripts/make_anki_listening.py
```

These scripts historically read `vocabulary.json` and `clips/`, then wrote
`output/N2Words.apkg` and `output/N2Words_listening.apkg`. Since
`vocabulary.json` is now retired as `vocabulary.json.db`, refresh these Anki
scripts to read `output/n2vocab.sqlite` before using them for a new deck build.

## Git Checkpoints

Before large cleanup or generation runs:

```bash
git status --short
git add <intentional files>
git commit -m "short factual message"
```

Do not commit Whisper models, source audio, generated clip folders, `.apkg` decks, or caches unless you are intentionally taking a large binary snapshot.
