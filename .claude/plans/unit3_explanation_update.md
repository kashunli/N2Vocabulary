# Plan: Re-generate Unit 3 Explanations with New Skill Format

## Goal

Update all 50 Unit 3 (形容詞A, indexes 221–270) sentence explanations to follow the new `japanese-sentence-explanation` skill format, then rebuild Anki decks.

## Current State

- All 50 entries have explanations already
- Existing format: freeform line-by-line breakdown (word = "meaning" — gloss)
- Target format: **bold translation** → `---` → structured bullet list with kanji+furigana, dictionary defs, transitive/intransitive markers, JLPT levels, semantic drift notes

## Steps

### 1. Batch Generate New Explanations (50 entries)

Split into batches of ~8–10 entries per subagent to avoid context overflow:
- Batch 1: entries 221–228 (有難い → 心細い)
- Batch 2: entries 229–237 (かわいそうな → うらやましい)
- Batch 3: entries 238–246 (情けない → 激しい)
- Batch 4: entries 247–255 (むなしい → 珍しい)
- Batch 5: entries 256–264 (おとなしい → 険しい)
- Batch 6: entries 265–270 (なまぬるい → きまり悪い)

Each subagent receives:
- The entry's sentence, headword, reading, meaning
- Instructions to produce output in the exact skill format
- Special attention to: adjective conjugations, wago vocabulary notes, Chinese false friends

### 2. Merge New Explanations

Save each batch as `output/explanations_unit3_batch_N.json`, then merge:
```bash
python parse/scripts/merge_explanations.py output/explanations_unit3_batch_1.json
# ... repeat for all batches
```

### 3. Rebuild Anki Decks

```bash
python parse/scripts/make_anki_listening.py
python parse/scripts/make_anki.py
```

### 4. Rebuild HTML Pages

```bash
python parse/scripts/make_html.py
```

## Output Files

- `output/explanations_unit3_batch_{1-6}.json` — merged explanation batches
- `output/vocabulary_db.json` — updated in place
- `output/N2Words_listening.apkg` — rebuilt deck
- `output/N2Words.apkg` — rebuilt deck
- `output/html/words/by_unit/unit_03.html` — re-rendered HTML

## Explanation Format Per Entry

```
**Natural English translation of the sentence.**

---

- **headword（よみ）** — dictionary definition, part of speech. [JLPT Nx]
- **grammar pattern** — function and nuance in this sentence. [JLPT Nx]
- ... (remaining words and patterns)
```

Key requirements:
- Show kanji form for words commonly written in kana
- Mark verbs as 他動詞/自動詞 with counterpart
- Flag adversative passives
- Note wago semantic drift
- Flag Chinese false friends
- No kanji breakdowns, no chunk tables, no summary
