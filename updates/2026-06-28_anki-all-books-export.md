# 2026-06-28 - All-book Anki exports

## What ran

Rebuilt word-card APKGs for every selectable book in
`wordService/data/n2vocab.sqlite`:

```powershell
python -u .\skills\makeAnkiCards\scripts\make_anki.py --book GWB_N2 --out output\GWB_N2Words.apkg
python -u .\skills\makeAnkiCards\scripts\make_anki.py --book N2 --out output\N2Words.apkg
python -u .\skills\makeAnkiCards\scripts\make_anki.py --book N2_1500 --out output\N2_1500Words.apkg
python -u .\skills\makeAnkiCards\scripts\make_anki.py --book N3 --out output\N3Words.apkg
```

## Exporter fix

`GWB_N2` had two kana-only rows where `kanji` was blank but `reading` was
present: source indexes `4568` (`さもないと`) and `4569` (`さらなる`). Anki did
not create cards for those notes because the required front `Headword` field was
empty. The exporter now falls back from `kanji` to `reading` for the rendered
headword, preserving the note while keeping the source data unchanged.

## Package verification

The APKG files were opened as zip files and their embedded Anki SQLite
collections were inspected directly.

| Package | Notes | Cards | Media | No-card notes | Missing word audio | Missing sentence audio |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `output/GWB_N2Words.apkg` | 3839 | 3839 | 7775 | 0 | 8 | 391 |
| `output/N2Words.apkg` | 1160 | 1160 | 5074 | 0 | 0 | 0 |
| `output/N2_1500Words.apkg` | 1591 | 1591 | 3193 | 0 | 0 | 1591 |
| `output/N3Words.apkg` | 869 | 869 | 3263 | 0 | 0 | 11 |

The `N2_1500` missing sentence-audio count is expected for the current deck
shape: main sentence audio is intentionally left out while word and extra
example/related-term audio are packaged.

## Follow-up pronunciation generation

Generated missing pronunciation media for the books whose APKGs had missing
word or example/sentence audio:

```powershell
python -u .\wordService\tools\generate_all_audio.py --base-url http://127.0.0.1:8798 --book GWB_N2 --book N2 --book N3 --kind all --progress-every 10 --timeout 240 --stop-on-error
```

The first service-backed run exposed a Windows SQLite file replacement race.
`wordService/rust/src/repository.rs` now writes generated audio metadata
directly to SQLite under the existing service write lock instead of replacing
the database file from inside the service process. The word-audio endpoint also
falls back to `reading` when the display word is blank or contains ASCII
letters, so imported rows such as `hot line`, `さもないと`, and `さらなる`
receive pronounceable Japanese audio.

`wordService/tools/generate_all_audio.py` now reads canonical
`book_entries`/`item_examples` rows, includes kana-only word rows, and records
resumable JSONL events under `wordService/audio_generation_runs/`.

Verification after generation:

| Book | Missing word audio | Missing example audio |
| --- | ---: | ---: |
| `GWB_N2` | 0 | 0 |
| `N2` | 0 | 0 |
| `N2_1500` | 0 | 0 |
| `N3` | 0 | 0 |

Rebuilt affected APKGs and inspected their embedded Anki collections:

| Package | Notes | Cards | Media | Missing word audio | Missing sentence audio with sentence text |
| --- | ---: | ---: | ---: | ---: | ---: |
| `output/GWB_N2Words.apkg` | 3839 | 3839 | 7846 | 0 | 0 |
| `output/N2Words.apkg` | 1160 | 1160 | 5132 | 0 | 0 |
| `output/N3Words.apkg` | 869 | 869 | 3271 | 0 | 0 |

`GWB_N2` still has 328 cards with blank `Sentence` and blank `SentenceAudio`,
and `N3` still has 11 such cards. These are source rows without main sentence
text, not failed audio-generation rows.

## N2_1500 sentence-audio re-export

At user request, `N2_1500` main sentence audio is now included in the word-card
deck as well. The APKG builder no longer suppresses `N2_1500` `SentenceAudio`
when SQLite points to a real clip.

Rebuilt and inspected:

| Package | Notes | Cards | Media | Missing word audio | Missing sentence audio with sentence text |
| --- | ---: | ---: | ---: | ---: | ---: |
| `output/N2_1500Words.apkg` | 1591 | 1591 | 4569 | 0 | 0 |

The remaining 233 blank `SentenceAudio` fields are rows that also have blank
`Sentence` fields.
