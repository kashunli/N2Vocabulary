# 2026-06-25 - Word-card group exports

## Why

The word-centered Anki deck should test whether the learner can recall the
reading and meaning from the written word alone. The previous front template
also showed reading and word audio, which made the recall target too easy.

The same SQLite words DB now stores multiple books (`N2`, `N2_1500`, `N3`,
`GWB_N2`) and word marks, so the N2 word-card builder can safely become the
shared exporter for small study groups instead of maintaining separate APKG
patch workflows for each source.

## What changed

- `skills/makeAnkiCards/scripts/make_anki.py` now shows only the headword on
  the front of word cards. Reading, audio, meanings, sentence, translation,
  explanations, and extra examples remain on the back.
- `skills/makeAnkiCards/scripts/generate_n2_1500_word_audio.py` generates
  dedicated `N2_1500` word audio from the kana reading field. This avoids
  wrong readings from kanji TTS and avoids reusing same-number clips from older
  books.
- `skills/makeAnkiCards/scripts/generate_n2_1500_example_audio.py` generates
  dedicated `N2_1500` audio for related terms and example phrases stored in
  `entry_examples`, then packages those clips on the back of the word cards.
- The builder accepts structured group filters:
  - `--book`
  - `--unit` (repeatable)
  - `--source-indexes`
  - `--flagged-only`
  - `--deck-name`
- The default full N2 export keeps the historical deck ID and
  `n2vocab_<index>` note GUIDs so Anki imports update the existing N2 notes.
- Non-N2 exports use book-scoped note GUIDs, which lets N2 and N3 cards coexist
  even when they share the same source indexes.

## Useful commands

```powershell
python -u .\skills\makeAnkiCards\scripts\make_anki.py
python -u .\skills\makeAnkiCards\scripts\generate_n2_1500_word_audio.py
python -u .\skills\makeAnkiCards\scripts\generate_n2_1500_example_audio.py
python -u .\skills\makeAnkiCards\scripts\make_anki.py --book N3 --out output\N3Words.apkg
python -u .\skills\makeAnkiCards\scripts\make_anki.py --book N2 --flagged-only --out output\N2Words_flagged.apkg --deck-name "耳から覚える::N2Words::Flagged"
python -u .\skills\makeAnkiCards\scripts\make_anki.py --book N2 --source-indexes 1-20,85,120-125 --out output\N2Words_custom.apkg
```

## N2_1500 export result

After regenerating word audio from readings and example audio from
`entry_examples`, `output/N2_1500Words.apkg` contains 1,591 notes and 2,510
media files:

- 1,591 packaged word-audio files in the `WordAudio` field.
- 919 packaged related-term/example-audio clips inside the `MoreExample*`
  back-side fields.
- 0 packaged main `SentenceAudio` fields.

SQLite `entries.word_clip` for `book_code = 'N2_1500'` now points to
`clips/n2_1500/words/n2_1500_word_<entry_id>.mp3`. SQLite
`entry_examples.audio_clip` for `book_code = 'N2_1500'` now points to
`clips/n2_1500/examples/n2_1500_example_<entry_id>_<position>.mp3`.

The generator keeps visible readings intact on the card, but strips notation
markers from spoken TTS text for cases such as `こうりょ（する）`,
`あくまで（も）`, and `～かん`.

## Residual notes

The existing N3Words APKG salvage tools are still useful for archaeology, but
new word-card exports should prefer the SQLite-backed N2Vocabulary builder when
the rows already exist in `wordService/data/n2vocab.sqlite`.
