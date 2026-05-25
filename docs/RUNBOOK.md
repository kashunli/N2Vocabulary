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

After cutting or repairing track folders, refresh the flat service aliases and
SQLite audio paths:

```bash
python skills/cutTwice/flatten_audio_clips.py
python skills/cutTwice/flatten_audio_clips.py --apply --migrate-db
```

The first command is an audit. The second copies `clips/words/wordNNN.mp3` and
`clips/sentences/sentenceNNN.mp3`, then updates the DB if every source index is
present and unambiguous.

## Study Words Runtime

```bash
cd wordService/rust
cargo run
```

This starts the local SQLite-backed word service at `http://127.0.0.1:8767/`.
It reads `output/n2vocab.sqlite`, serves audio from `clips/`, and persists
known/flagged card marks back into the same SQLite database.

Useful routes:

```text
http://127.0.0.1:8767/
http://127.0.0.1:8767/api/summary
http://127.0.0.1:8767/api/units
http://127.0.0.1:8767/api/entries?unit=1
```

## Anki Decks

The built decks live under `output/`. The active Anki build scripts live under `skills/makeAnkiCards/scripts/`.

```bash
python skills/makeAnkiCards/scripts/make_anki.py
python skills/makeAnkiCards/scripts/make_anki_listening.py
```

These scripts read `output/n2vocab.sqlite` and `clips/`, then write
`output/N2Words.apkg` and `output/N2Words_listening.apkg`.

## Git Checkpoints

Before large cleanup or generation runs:

```bash
git status --short
git add <intentional files>
git commit -m "short factual message"
```

Do not commit Whisper models, source audio, generated clip folders, `.apkg` decks, or caches unless you are intentionally taking a large binary snapshot.
