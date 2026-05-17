# Skill: Runtime Words & Static Exercises

Use the SQLite-backed runtime server for N2 vocabulary words, and rebuild the
static exercise pages when OCR exercise JSON changes.

## What this skill manages


```
wordsAndExerciseInHtml/
  runtime_word_pages.py           ← server-side word-page templates
  build_words.py                  ← optional static long-page snapshot builder
  build_word_cards.py             ← optional static card-page snapshot builder
  words/                          ← old/static snapshots; runtime pages come from SQLite
    index.html
    by_unit/
      unit_01.html … unit_13.html
    cards/
      index.html
      unit_01.html … unit_13.html
  exercises/
    index.html
    n2/
      unit01/ … unit13/           ← unit exercise pages with answer keys
      matome1/                    ← summary exercise pages
```

## Data sources

| What | Path | Notes |
|------|------|-------|
| Vocabulary text | `output/n2vocab.sqlite` | Runtime and static snapshot source of truth for N2 word pages |
| Retired JSON snapshot | `vocabulary.json.db` (project root) | Historical reference only; do not use as the live import source |
| Audio clips | `clips/unitX_trackYY/wordN.mp3` + `sentenceN.mp3` (project root) | separate word and sentence files |
| Known/flagged marks | `output/n2vocab.sqlite`, table `word_marks` | Runtime mark store |
| Exercise JSON | `json/page_*.json` | parsed OCR pages, type=exercise/answer_key |

### Retired JSON snapshot shape

```json
{
  "index": 1,
  "unit": { "number": 1, "header": "Unit 01 名詞 A" },
  "reading": "じんせい",
  "kanji": "人生",
  "headword_text": "人生",
  "meaning_en": "",
  "meaning_zh": "",
  "sentence": "幸せな人生を送る。",
  "examples": ["人生経験が豊富な人の話は面白い。"],
  "word_clip": "clips/unit1_track02/word001.mp3",
  "sentence_clip": "clips/unit1_track02/sentence001.mp3",
  "explanation": "**To live...** \n\n---\n\n- **人生** — noun..."
}
```

> **Note:** This shape documents the retired `vocabulary.json.db` snapshot for archaeology only. Current word pages read SQLite.
> `word_clip`/`sentence_clip` paths are relative to the project root, e.g. `clips/unit1_track02/word001.mp3`.
> Subdirectory names follow the pattern `unitX_trackYY`; numbering is global across the whole book.

### SQLite example schema

In SQLite, sentence-level content is normalized into `entry_examples`:

- `position = 0` is the main sentence for the entry.
- `position = 1+` are additional example sentences or patterns.
- `translation_en` and `translation_zh` store example translations.
- `explanation_md` and `audio_clip` belong to the example row when available.

`load_entries()` keeps the legacy builder shape by exposing position `0` as
`sentence`, `sentence_translation_en`, `sentence_translation_zh`, `sentence_clip`,
and `explanation`, while `examples` contains positions `1+`.

## Run word pages

Run from the **project root**:

```bash
python marks_server.py
```

Open:

```text
http://127.0.0.1:8766/words/index.html
http://127.0.0.1:8766/words/cards/index.html
```

`marks_server.py` renders word pages from `output/n2vocab.sqlite` at request
time. It also serves `clips/...` audio and persists card marks into the
`word_marks` SQLite table.

## Optional static word snapshots

The static builders still reuse the same visual templates, but they are no
longer the normal study entrypoint:

```bash
python wordsAndExerciseInHtml/build_words.py
python wordsAndExerciseInHtml/build_word_cards.py
```

Use these only when you intentionally want regenerated HTML snapshots under
`wordsAndExerciseInHtml/words/`.

## Rebuild exercise pages

Exercise pages are still generated as static pages:

```bash
python wordsAndExerciseInHtml/build_exercises.py
```

That script reads `json/page_*.json` (OCR output) and writes into
`wordsAndExerciseInHtml/exercises/`. The runtime server serves those files
unchanged under `/exercises/...`.

## When to rebuild

- **After changing word data in SQLite** → restart or refresh `marks_server.py`; pages render live from the DB
- **After changing SQLite import logic** → run the import/repair script that owns that change, then refresh the browser
- **After new audio clips are cut** → make sure SQLite `word_clip` / `sentence_clip` paths point at `clips/...`
- **After re-OCRing exercise pages** → run `python wordsAndExerciseInHtml/build_exercises.py`

## Audio path resolution

Clips are at `clips/unitX_trackYY/wordN.mp3` (and `sentenceN.mp3`) relative to the project root.
In runtime pages, audio is served from the project root under `/clips/...`.
In optional static snapshots from `wordsAndExerciseInHtml/words/by_unit/`,
that's three levels up:

```
../../../clips/unit1_track02/word001.mp3
```

`build_words.py` handles the static snapshot case via `clip_rel_path()` which
prepends `../../../` to the path stored in SQLite.

## Explanation markdown format

The `explanation` field uses lightweight markdown rendered by `explanation_html()`:

| Syntax | Output |
|--------|--------|
| `**text**` | `<strong>` bold |
| `*text*` | `<em>` italic |
| `- item` | `<ul><li>` list |
| `\n---\n` | `<hr>` section divider |
| `[JLPT N2]` | styled badge |

## Adding a new unit

1. Add/import entries into `output/n2vocab.sqlite` with the correct unit number and header
2. Add audio clips to `clips/unitX_trackYY/` following the `wordN.mp3` / `sentenceN.mp3` naming convention
3. Refresh `marks_server.py`; the runtime routes pick up the new unit from SQLite
