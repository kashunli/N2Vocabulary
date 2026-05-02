---
name: batch-japanese-sentence-explanations
description: Generate batch Japanese sentence explanations through the DeepSeek API for N2Vocabulary-style Anki data. Use when Codex needs to explain many Japanese example sentences, fill or refresh `explanation` fields in `vocabulary.json`, produce merge-ready explanation JSON, or call DeepSeek `deepseek-v4-flash` with `DEEPSEEK_API_KEY` from the Windows environment.
---

# Batch Japanese Sentence Explanations

Use this skill to generate compact Markdown explanations for Japanese sentences in batches, especially for `D:\n2Prepare\materialToLearn\N2Vocabulary\vocabulary.json`.

## Quick Start

Run the bundled script from the repo root:

```powershell
python .\batch-japanese-sentence-explanations\scripts\batch_explain_deepseek.py `
  --input .\vocabulary.json `
  --output-dir .\output\deepseek_explanation_batches `
  --skip-existing `
  --limit 20
```

The script reads `DEEPSEEK_API_KEY` from the current process environment first, then falls back to the persistent Windows User and Machine environment variable registry locations. It calls DeepSeek's OpenAI-compatible `/chat/completions` endpoint and writes separate review files:

```
output/deepseek_explanation_batches/
├── selected_records.json       # dry-run only
├── batch_0001.json             # one merge-ready JSON array per API batch
├── batch_0002.json
├── all_explanations.json       # combined review copy
└── manifest.json               # progress, model, token usage
```

Do not edit `vocabulary.json` during generation. Review the batch files first, then merge a chosen batch or `all_explanations.json` later with the repo helper if desired.

## Workflow

1. Check that `DEEPSEEK_API_KEY` exists in the current process env, Windows User env, or Windows Machine env.
2. Select a small batch first with `--limit 5 --dry-run` and inspect `selected_records.json`.
3. Keep `--skip-existing` on when filling gaps in `vocabulary.json`.
4. Increase `--batch-size` only after the style looks good; `10` to `25` is usually comfortable.
5. Generate into a dated or purpose-named `--output-dir` so progress is easy to monitor.
6. Merge only reviewed output into `vocabulary.json` in a separate later step.

## Input Shapes

The script accepts:

- `vocabulary.json`: an array of objects with `index`, `sentence`, and optional `explanation`.
- Generic JSON array of strings.
- Generic JSON array of objects with `sentence`, `text`, `japanese`, or `ja`.
- JSON object with a `sentences` array.

Useful options:

- `--skip-existing`: omit objects whose `explanation` field is already non-empty.
- `--start-index N`: only include vocabulary entries whose `index >= N`.
- `--end-index N`: only include vocabulary entries whose `index <= N`.
- `--limit N`: cap the selected records for a test or small run.
- `--batch-size N`: number of sentences per API request.
- `--output-dir PATH`: write `batch_0001.json`, `all_explanations.json`, and `manifest.json`.
- `--output PATH`: optional single combined JSON file.
- `--model deepseek-v4-flash`: default model.
- `--thinking enabled`: opt into thinking mode if needed; default is `disabled` for cleaner formatting.

## Explanation Style

Use `references/explanation_prompt.md` as the style contract. The bundled script embeds the same core prompt and asks DeepSeek to return valid JSON so the result can be merged safely.

Each explanation should contain:

1. Bold natural English translation
2. Horizontal rule `---`
3. Bullet list with no header

Keep notes concise, sentence-anchored, and aimed at a Chinese native speaker at JLPT N2-N3 level with strong kanji literacy.

## DeepSeek API Notes

Use `references/deepseek_api_notes.md` if the API call needs adjustment. The important defaults are:

- Base URL: `https://api.deepseek.com`
- Endpoint: `/chat/completions`
- Model: `deepseek-v4-flash`
- Environment key: `DEEPSEEK_API_KEY`
- JSON response mode: `response_format: {"type": "json_object"}`

Do not store the API key in this skill or in output files.
