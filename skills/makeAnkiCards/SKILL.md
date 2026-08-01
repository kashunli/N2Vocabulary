---
name: make-anki-cards
description: Build, inspect, or repair the N2 Vocabulary Anki deck outputs using the current SQLite database and service-facing audio clips. Use when working on N2Words.apkg, N2Words_listening.apkg, card templates, media references, deck exports, or Anki validation for this repository.
---

# Make Anki Cards

This is the project-local Anki workflow for `D:\n2Prepare\N2Vocabulary`.
Keep it inside `skills/makeAnkiCards/`, because the deck builders depend on the
current project contract: `wordService/data/n2vocab.sqlite`, flat clip aliases under
`clips/`, and the same card identity used by prior N2 decks.

## Current Source Of Truth

- **Vocabulary and explanations**: `wordService/data/n2vocab.sqlite`
- **Word audio**: `clips/words/word<entry_id>.mp3`
- **Main sentence audio**: `clips/sentences/sentence<entry_id>.mp3`
- **Generated sentence audio**: `clips/generated_sentences/edge_tts/`
- **SQLite audio fields**: book-specific `book_entries.word_clip` with
  `vocabulary_items.word_clip` as a compatibility fallback, plus
  `book_entries.sentence_clip` and `item_examples.audio_clip`
- **Example translations**: `item_examples.translation_en`; use
  `item_examples.kind` to distinguish the main sentence from extra examples
  and related terms
- **Deck outputs**: `output/N2Words.apkg` and `output/N2Words_listening.apkg`

The builders call `db.connect.load_entries()`, which reads SQLite with
`immutable=1` and returns the old list-of-dicts shape. This preserves the
existing templates and stable Anki note GUID formulas while using current DB
content.

## Scripts

- `scripts/make_anki.py` builds the word-centered deck.
  - Deck name: `耳から覚える::N2Words`.
  - The front side is a recall prompt with only the headword, so reading,
    audio, meanings, sentence, and explanations stay on the back.
  - The Anki template does not loop over database rows. The script pre-renders
    extra examples into five ordered fields: `MoreExample1` through
    `MoreExample5`. Extra example 6+ is intentionally omitted.
  - Japanese sentence fields are rendered through `scripts/anki_render.py`, so
    kanji-bearing tokens get `<ruby><rt>...</rt></ruby>` furigana.
  - The same template can export other `book_entries.book_code` groups from the
    words DB with `--book`, including `N1`, `N3`, `N2_1500`, and `GWB_N2`.
  - `N2_1500` main sentence audio is allowed only when SQLite explicitly names
    a `sentence_clip`. Do not use source-index filename fallback for imported
    books; that was the older path that could accidentally pick up another
    book's sentence clip.
  - Extra examples can carry their own `item_examples.audio_clip` media. Those
    clips are rendered inside `MoreExample1` through `MoreExample5` on the back,
    separate from the main `SentenceAudio` field.
- `scripts/generate_n2_1500_word_audio.py` generates dedicated `N2_1500` word
  audio from the kana `reading` field, not from kanji. Use it before exporting
  `N2_1500` cards when word audio is missing or suspect.
- `scripts/generate_n2_1500_example_audio.py` generates dedicated `N2_1500`
  audio for the related terms and example phrases stored in `item_examples`.
  It writes under `clips/n2_1500/examples/` and updates
  `item_examples.audio_clip`.
- `scripts/make_anki_listening.py` builds the listening deck.
  - Deck name: `耳から覚える::N2WordsSentences`.
  - The front side now follows the word-card style: headword only. Sentence
    audio, sentence text, translations, reading, word audio, meanings, and
    explanations stay on the back.
  - The back side shows the main sentence English translation and the same
    pre-rendered translated/explained extra examples in `MoreExample1` through
    `MoreExample5`.
  - It uses the same furigana renderer for the main sentence and extra example
    sentences.
  - The same script can export `N3` with book-scoped deck and note identities.
- `scripts/make_clean_db.py` and `scripts/merge_explanations.py` are legacy
  helpers kept only for archaeology unless the user explicitly asks to repair
  old JSON-era data.

Do not add new Anki logic as loose root scripts. Keep deck code in this folder.

## Before Rebuilding

Run these commands from `D:\n2Prepare\N2Vocabulary` if audio clips may have
changed:

```powershell
python skills/cutTwice/flatten_audio_clips.py
python skills/cutTwice/flatten_audio_clips.py --apply --migrate-db
```

The dry run checks whether track-folder clips can be copied into flat service
aliases. The apply run copies aliases and updates SQLite audio columns only
after the sources are complete and unambiguous.

## Build Commands

Run from `D:\n2Prepare\N2Vocabulary`:

```powershell
python -u .\skills\makeAnkiCards\scripts\make_anki.py
python -u .\skills\makeAnkiCards\scripts\make_anki_listening.py
```

Optional explicit form:

```powershell
python -u .\skills\makeAnkiCards\scripts\make_anki.py --db wordService\data\n2vocab.sqlite --clips clips --out output\N2Words.apkg
python -u .\skills\makeAnkiCards\scripts\make_anki_listening.py --db wordService\data\n2vocab.sqlite --clips clips --out output\N2Words_listening.apkg
```

Group export examples:

```powershell
python -u .\skills\makeAnkiCards\scripts\make_anki.py --book N1 --out output\N1Words.apkg
python -u .\skills\makeAnkiCards\scripts\make_anki.py --book N3 --out output\N3Words.apkg
python -u .\skills\makeAnkiCards\scripts\make_anki_listening.py --book N3 --out output\N3Words_listening.apkg
python -u .\skills\makeAnkiCards\scripts\make_anki.py --book N2 --flagged-only --out output\N2Words_flagged.apkg --deck-name "耳から覚える::N2Words::Flagged"
python -u .\skills\makeAnkiCards\scripts\make_anki.py --book N2_1500 --unit 1 --unit 2 --out output\N2_1500_units01-02.apkg
python -u .\skills\makeAnkiCards\scripts\make_anki.py --book N2 --source-indexes 1-20,85,120-125 --out output\N2Words_custom.apkg
```

These group exports still read from `wordService/data/n2vocab.sqlite` and use
the same word-card template. The full `N2` export keeps the historical deck ID
and `n2vocab_<index>` note GUID formula; non-N2 books use book-scoped GUIDs so
N2 and N3 cards can coexist in Anki without source-index collisions. Filename
fallback for media is intentionally limited to the original `N2` deck; imported
books must use explicit SQLite clip paths to avoid cross-book audio matches.

For a clean `N2_1500` word-audio refresh:

```powershell
python -u .\skills\makeAnkiCards\scripts\generate_n2_1500_word_audio.py --dry-run
python -u .\skills\makeAnkiCards\scripts\generate_n2_1500_word_audio.py
python -u .\skills\makeAnkiCards\scripts\generate_n2_1500_example_audio.py --dry-run
python -u .\skills\makeAnkiCards\scripts\generate_n2_1500_example_audio.py
python -u .\skills\makeAnkiCards\scripts\make_anki.py --book N2_1500 --out output\N2_1500Words.apkg
```

The word generator writes MP3 files under `clips/n2_1500/words/` and updates
only `vocabulary_items.word_clip` for `book_code = 'N2_1500'`. The example generator
writes MP3 files under `clips/n2_1500/examples/` and updates only
`item_examples.audio_clip` for `book_code = 'N2_1500'`.

## Validation

- Confirm both builders print the expected note count.
- Confirm media counts and missing audio counts.
- Inspect the `.apkg` files as zip archives if media embedding is uncertain.
- Preserve stable deck IDs, model IDs, and `genanki.guid_for(...)` formulas
  unless the user explicitly wants a new deck identity.
- Treat SQLite and flat clip aliases as authoritative. Filename search is only
  fallback behavior for older data.

## Study-Ready Outputs

Use the deck files in `output/` directly:

- `output/N2Words.apkg`
- `output/N2Words_listening.apkg`
