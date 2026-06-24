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
It reads `wordService/data/n2vocab.sqlite`, serves audio from `clips/`, and persists
known/flagged card marks back into the same SQLite database.

Useful routes:

```text
http://127.0.0.1:8767/
http://127.0.0.1:8767/api/summary
http://127.0.0.1:8767/api/units
http://127.0.0.1:8767/api/entries?unit=1
```

## Debug A Bad Vocabulary Row

When the browser shows a wrong word, reading, sentence, or example, treat
`wordService/data/n2vocab.sqlite` as the first source to inspect. The UI word number
usually maps to `entries.source_index`, and the main sentence is duplicated in
`entries.sentence` and `entry_examples.position = 0`.

This command prints the entry and all examples for a specific word. Replace the
unit and source index values as needed:

```powershell
@'
import sqlite3
from pathlib import Path

db = Path("wordService/data/n2vocab.sqlite")
unit_number = 12
source_index = 1025

conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
entry = conn.execute(
    """
    SELECT entry_id, source_index, unit_number, position,
           kanji, reading, verb_pattern,
           meaning_en, meaning_zh, sentence, word_clip, sentence_clip
    FROM entries
    WHERE book_code = 'N2' AND unit_number = ? AND source_index = ?
    """,
    (unit_number, source_index),
).fetchone()

print(dict(entry) if entry else "No matching entry")
if entry:
    for row in conn.execute(
        """
        SELECT position, text, translation_en, translation_zh, audio_clip
        FROM entry_examples
        WHERE entry_id = ?
        ORDER BY position
        """,
        (entry["entry_id"],),
    ):
        print(dict(row))
'@ | python -
```

Before applying a manual correction, copy the database:

```powershell
@'
from datetime import datetime
from pathlib import Path
import shutil

db = Path("wordService/data/n2vocab.sqlite")
backup = db.with_name(f"n2vocab.sqlite.backup_before_manual_fix_{datetime.now():%Y%m%d_%H%M%S}")
shutil.copy2(db, backup)
print(backup)
'@ | python -
```

Correction checklist:

- Update `entries.kanji`, `entries.reading`, meanings, `entries.sentence`,
  and `entries.explanation_md` together when the headword itself is wrong.
- Keep `entry_examples.position = 0` aligned with `entries.sentence`.
- Put screenshot/book example sentences in later `entry_examples` positions.
- Clear `entry_examples.audio_clip` for any changed generated example so lazy
  TTS can regenerate from the corrected text.
- Run `cd wordService/rust` then `cargo test` after changing data that the
  service depends on.

## Anki Decks

The built decks live under `output/`. The active Anki build scripts live under `skills/makeAnkiCards/scripts/`.

```bash
python skills/makeAnkiCards/scripts/make_anki.py
python skills/makeAnkiCards/scripts/make_anki_listening.py
```

These scripts read `wordService/data/n2vocab.sqlite` and `clips/`, then write
`output/N2Words.apkg` and `output/N2Words_listening.apkg`.

## Git Checkpoints

Before large cleanup or generation runs:

```bash
git status --short
git add <intentional files>
git commit -m "short factual message"
```

Do not commit Whisper models, source audio, generated clip folders, `.apkg` decks, or caches unless you are intentionally taking a large binary snapshot.
