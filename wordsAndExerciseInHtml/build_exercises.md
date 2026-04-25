# Skill: Build HTML Exercises

Rebuild the interactive exercise HTML pages for N2 vocabulary (unit drills + matome sets).

## What this skill manages

```
wordsAndExerciseInHtml/
  build_exercises.py              ← THIS SCRIPT
  exercises/
    index.html                    ← top-level nav (manually maintained)
    n2/
      index.html                  ← auto-generated guide page (--build-index)
      unit01/
        unit01_with_answers_1.html
        unit01_with_answers_2.html
        unit01_with_answers_3.html
      unit02/ … unit13/
      matome1/
        matome1_with_answers_1.html
        matome1_with_answers_2.html
```

## Two-step pipeline

### Step 1 — Python: OCR JSON → enriched JSON

**Script:** `parse/scripts/convert_n2_exercises.py`
**Reads:** `json/page_*.json` — OCR'd book pages tagged as `page_type: "exercise"` or `"answer_key"`
**Writes:** `D:/n2Prepare/tools/exercisesFromJSON/data/n2/{unit}/` enriched JSON files

The script has a hardcoded `GROUPS` array mapping (unit, word-range, set-number) to specific
page numbers. Each group produces one `{unit}_with_answers_{set}.json`.

### Step 2 — Node.js: enriched JSON → HTML

**Script:** `D:/n2Prepare/tools/exercisesFromJSON/scripts/json_to_test.js`
**Reads:** `data/n2/**/*.json` (Step 1 output)
**Writes:** `wordsAndExerciseInHtml/exercises/n2/**/*.html` + `exercises/n2/index.html`

Renders interactive exercise pages with answer-checking UI (particle fill-in, checkbox word
selection, multiple choice, token-bank, verb conjugation tables).

## Rebuild exercises (full pipeline)

Run from the **project root**:

```bash
python wordsAndExerciseInHtml/build_exercises.py
```

### Partial rebuilds

```bash
# Only regenerate enriched JSON (skip HTML)
python wordsAndExerciseInHtml/build_exercises.py --json-only

# Only regenerate HTML from existing JSON (skip OCR parsing)
python wordsAndExerciseInHtml/build_exercises.py --html-only

# Debug answer-key parsing
python wordsAndExerciseInHtml/build_exercises.py --json-only --debug-ak
```

## Raw material sources

| Source | Location | Description |
|--------|----------|-------------|
| Exercise pages | `json/page_NNN.json` with `"page_type": "exercise"` | OCR'd drill questions |
| Answer key pages | `json/page_NNN.json` with `"page_type": "answer_key"` | Answers (pages ~283–287) |
| Page groups config | `convert_n2_exercises.py` `GROUPS` array (line 30) | Maps page numbers to unit/set |

### exercise page JSON schema

```json
{
  "page": 15,
  "page_type": "exercise",
  "section": "Unit 01 名詞 A 練習問題 I",
  "exercises": [
    {
      "label": "I",
      "instruction": "( ) に助詞を書きなさい。",
      "questions": ["1. 私は大学で...", "2. 家族 ( ) 苦労..."],
      "word_list": ["敵", "味方", ...],
      "options": [...]
    }
  ],
  "raw_text": "flat OCR fallback if exercises array empty"
}
```

### answer key page JSON schema

```json
{
  "page": 283,
  "page_type": "answer_key",
  "raw_text": "Unit 01\n1～50\n練習問題Ⅰ\nⅠ\n1. を\n2. に、を\nⅡ\n1. 味方\n..."
}
```

## Exercise types rendered by json_to_test.js

| Type | Instruction keyword | UI |
|------|--------------------|----|
| A | 助詞を書きなさい | Text input blanks |
| B | ○を付けなさい | Checkbox word grid |
| C | 〔 〕の中から選ぶ | Inline pill options |
| E | 反対の意味 | Text input |
| F | 最も近い | Multiple choice |
| G | Token bank fill-in | Clickable token bank |
| H | Verb pairs / conjugation | Verb table |
| K | a/b/c/d choice | Radio pills |

## Adding a new exercise set

1. Ensure the relevant pages in `json/` have `"page_type": "exercise"` or `"answer_key"`
2. Add an entry to the `GROUPS` array in `convert_n2_exercises.py`:
   ```python
   ("unit14", 14, "カテゴリ", "1161–1200", 1, [page_num1, page_num2]),
   ```
3. Run `python wordsAndExerciseInHtml/build_exercises.py`

## Dependencies

- Python 3.9+
- Node.js (for `json_to_test.js`)
- `D:/n2Prepare/tools/exercisesFromJSON/` — the exercisesFromJSON tool must be present
