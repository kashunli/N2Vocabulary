---
name: batch-japanese-sentence-explanations
description: Generate batch Japanese sentence explanations through the DeepSeek API for N2Vocabulary-style Anki data. Use when Codex needs to explain many Japanese example sentences, fill or refresh explanation fields, produce merge-ready explanation JSON, or call DeepSeek `deepseek-v4-flash` with `DEEPSEEK_API_KEY` from the Windows environment.
---

# Batch Japanese Sentence Explanations

Use this skill to generate reviewable Markdown explanations for Japanese sentences in batches, especially for N2Vocabulary data. The default English prompt/style contract lives in `references/explanation_prompt.md`; the all-Chinese prompt lives in `references/explanation_prompt_zh.md`. The Python script reads the chosen Markdown file so prompt edits do not need code edits.

The current repair workflow targets weak main-sentence explanations in `wordService/data/n2vocab.sqlite`. Generation writes JSON review files first; database writes require an explicit `--apply` and create backups.

## Quick Start

Run the bundled script from the repo root to select weak main-sentence explanations without calling DeepSeek:

```powershell
python .\skills\batch-japanese-sentence-explanations\scripts\batch_explain_deepseek.py `
  --source sqlite-main-sentences `
  --db .\wordService\data\n2vocab.sqlite `
  --output-dir .\output\sentence_explanation_redo_preview `
  --selection worst-first `
  --redo-fraction 0.5 `
  --dry-run `
```

Generate reviewed batch files:

```powershell
python .\skills\batch-japanese-sentence-explanations\scripts\batch_explain_deepseek.py `
  --source sqlite-main-sentences `
  --db .\wordService\data\n2vocab.sqlite `
  --output-dir .\output\sentence_explanation_redo_2026-06-09 `
  --selection worst-first `
  --redo-fraction 0.5
```

Generate all-Chinese explanations:

```powershell
python .\skills\batch-japanese-sentence-explanations\scripts\batch_explain_deepseek.py `
  --source json `
  --input .\path\to\sentences.json `
  --output-dir .\output\sentence_explanations_zh_2026-06-11 `
  --prompt-preset chinese
```

Apply reviewed output only after inspection:

```powershell
python .\skills\batch-japanese-sentence-explanations\scripts\batch_explain_deepseek.py `
  --source sqlite-main-sentences `
  --db .\wordService\data\n2vocab.sqlite `
  --output-dir .\output\sentence_explanation_redo_2026-06-09 `
  --apply
```

The script reads `DEEPSEEK_API_KEY` from the current process environment first, then falls back to the persistent Windows User and Machine environment variable registry locations. It calls DeepSeek's OpenAI-compatible `/chat/completions` endpoint and writes separate review files:

```
output/deepseek_explanation_batches/
├── selected_records.json       # selected rows and quality reasons
├── completed_records.json      # rows successfully generated
├── remaining_records.json      # not selected yet plus failed/unfinished rows
├── run_summary.json            # selection, generation, and apply ledger
├── batch_0001.json             # one reviewable JSON array per API batch
├── batch_0002.json
├── all_explanations.json       # combined review copy
├── manifest.json               # progress, model, token usage
├── generation_errors.json      # batch errors, if any
├── original_explanations_backup.json  # written by --apply
├── apply_summary.json          # written by --apply
└── n2vocab.sqlite.before_sentence_explanation_redo_*.bak
```

Do not edit the source data during generation. Review the batch files first, then merge a chosen batch or `all_explanations.json` later with the repo helper if desired.

## Workflow

1. Check that `DEEPSEEK_API_KEY` exists in the current process env, Windows User env, or Windows Machine env.
2. Select a small batch first with `--source sqlite-main-sentences --redo-count 5 --dry-run` and inspect `selected_records.json`.
3. Generate into a dated or purpose-named `--output-dir` so progress is easy to monitor.
4. Keep `--batch-size` at the default `5`; the script refuses values above `--max-batch-size 10`.
5. Review `batch_*.json` or `all_explanations.json`.
6. Apply only reviewed output with `--apply`; the apply step backs up the DB and original explanations first.

## Input Shapes

The script accepts:

- `--source sqlite-main-sentences`: selects weak, nonblank main-sentence explanations from SQLite.
- `vocabulary.json`: an array of objects with `index`, `sentence`, and optional `explanation`.
- Generic JSON array of strings.
- Generic JSON array of objects with `sentence`, `text`, `japanese`, or `ja`.
- JSON object with a `sentences` array.

Useful options:

- `--db PATH`: SQLite database for `sqlite-main-sentences`; defaults to `wordService/data/n2vocab.sqlite`.
- `--quality conservative`: select likely weak main-sentence explanations.
- `--selection worst-first`: sort weak rows by structural problems first, then shortest explanations, then source order.
- `--redo-fraction N`: select a fraction of eligible weak rows; use `0.5` for half.
- `--redo-count N`: exact selected row count; overrides `--redo-fraction`.
- `--exclude-completed PATH`: skip rows listed in a previous `completed_records.json` or `run_summary.json`.
- `--skip-existing`: omit objects whose `explanation` field is already non-empty.
- `--start-index N`: only include vocabulary entries whose `index >= N`.
- `--end-index N`: only include vocabulary entries whose `index <= N`.
- `--limit N`: cap the selected records for a test or small run.
- `--batch-size N`: number of sentences per API request; default `5`.
- `--max-batch-size N`: hard limit; default `10`.
- `--parallel N`: number of DeepSeek batch calls in flight; default `5`.
- `--output-dir PATH`: write `batch_0001.json`, `all_explanations.json`, and `manifest.json`.
- `--output PATH`: optional single combined JSON file.
- `--model deepseek-v4-flash`: default model.
- `--thinking enabled`: default thinking mode for higher-quality sentence repair. The request omits an explicit thinking level so DeepSeek uses its default level.
- `--prompt-preset english|chinese`: built-in style prompt when `--prompt` is not set. Default `english` uses `references/explanation_prompt.md`; `chinese` uses `references/explanation_prompt_zh.md`.
- `--prompt PATH`: optional Markdown prompt/style contract. Overrides `--prompt-preset`.
- `--force`: regenerate existing batch files instead of reusing matching ones.
- `--apply`: apply reviewed explanations to SQLite and write backups.

## Quality Filter

The conservative SQLite filter only selects `entry_examples.position = 0` rows whose old explanation is nonblank and likely weak. Reasons include:

- `length_lt_180`
- `missing_separator`
- `too_few_bullets`
- `english_first`
- `missing_target_word`
- `placeholder_translation_label`
- `malformed_markdown`

Each selected row records its `quality_reasons`, source identity, sentence, translation, and `old_explanation_md`.

For the first half-run, use `--selection worst-first --redo-fraction 0.5`. The current conservative selector finds 815 weak main sentences, so this selects 408 rows and leaves 407 in `remaining_records.json`.

## Resume Records

Every run writes durable progress files:

- `selected_records.json`: exact rows selected for this run.
- `completed_records.json`: rows that have finished DeepSeek generation and are ready for review/apply.
- `remaining_records.json`: weak rows not selected yet, plus failed or unfinished selected rows.
- `run_summary.json`: selection settings, total weak rows, selected/completed/remaining counts, usage, and apply results.

To continue later, pass a previous completion ledger:

```powershell
python .\skills\batch-japanese-sentence-explanations\scripts\batch_explain_deepseek.py `
  --source sqlite-main-sentences `
  --selection worst-first `
  --redo-fraction 1.0 `
  --exclude-completed .\output\sentence_explanation_redo_2026-06-09\completed_records.json `
  --output-dir .\output\sentence_explanation_redo_remaining_2026-06-10
```

## Apply Safety

`--apply` is SQLite-only and requires a review output directory. It refuses to apply when the SQLite WAL sidecar has content, copies the database to a timestamped `.bak`, writes `original_explanations_backup.json`, and keeps `entry_examples.explanation_md` plus `entries.explanation_md` synced for main sentences.

## Explanation Style

Use `references/explanation_prompt.md` as the default English style contract. Use `--prompt-preset chinese` for the all-Chinese style in `references/explanation_prompt_zh.md`. The bundled script reads the chosen file and adds only JSON-output instructions around it, so the Markdown prompt is the source of truth for prompt quality.

Each explanation should contain:

1. Bold natural English translation
2. Horizontal rule `---`
3. Bullet list with no header

Keep notes sentence-anchored and aimed at Joseph: a Chinese native speaker at JLPT N2-N3 level with strong kanji literacy. Explain the target word, necessary grammar, important particles/collocations, Chinese-reader traps, and standard kanji + furigana memory anchors even for words commonly written in kana. For word and phrase bullets, give the direct English counterpart for the meaning used in the sentence first, not a broad dictionary list.

For the Chinese prompt, explanations should be fully Chinese:

1. Bold natural Chinese translation
2. Horizontal rule `---`
3. Bullet list with no header

Keep the same sentence-anchored teaching logic, but use Chinese direct counterparts and Chinese explanations throughout.

## DeepSeek API Notes

Use `references/deepseek_api_notes.md` if the API call needs adjustment. The important defaults are:

- Base URL: `https://api.deepseek.com`
- Endpoint: `/chat/completions`
- Model: `deepseek-v4-flash`
- Thinking: `enabled`, with no explicit thinking level so the API default is used
- Environment key: `DEEPSEEK_API_KEY`
- JSON response mode: `response_format: {"type": "json_object"}`

Do not store the API key in this skill or in output files.
