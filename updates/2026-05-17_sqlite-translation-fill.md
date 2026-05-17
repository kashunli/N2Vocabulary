# 2026-05-17 - SQLite Translation Fill

## Why

`output/n2vocab.sqlite` has many N2 entries where both `meaning_en` and `meaning_zh` are blank. The word pages and Anki-style views already read those fields, so filling them in the SQLite source is cleaner than patching generated HTML.

Current read-only snapshot from WSL:

- N2 total entries: `1160`
- Missing English: `1133`
- Missing Chinese: `1133`
- Missing either field: `1133`

## Decision

Use `updates/` for the job record because this is a one-time data fill, not a permanent workflow. Keep the reusable API calling knowledge separately in `skills/aliyun-openai-compatible-api/`, since Aliyun Model Studio calls will likely be useful again.

## Job Script

One-time helper:

```bash
python3 updates/2026-05-17_sqlite_translation_fill.py --dry-run --limit 5
```

Trial API run:

```bash
python3 updates/2026-05-17_sqlite_translation_fill.py --limit 5 --batch-size 5
```

Full review generation:

```bash
python3 updates/2026-05-17_sqlite_translation_fill.py --batch-size 20
```

Apply reviewed output to the database:

```bash
python3 updates/2026-05-17_sqlite_translation_fill.py --apply --batch-size 20
```

The script reads `DASHSCOPE_API_KEY` from the process environment or `~/.config/n2vocab/env`. It uses Aliyun Model Studio's OpenAI-compatible endpoint with `deepseek-v4-flash`.

## Safety Notes

- API outputs are written under `output/translation_fill_2026-05-17/`.
- `selected_records.json`, `batch_*.json`, `all_translations.json`, and `manifest.json` are review artifacts.
- Database writes require `--apply`.
- Before replacing `output/n2vocab.sqlite`, the script creates a timestamped backup under the output folder.
- WSL had trouble opening the Windows-mounted SQLite file with normal locking, so the script reads with immutable read-only mode and applies updates through a temp working copy plus backup.

## Result

Generated and applied on 2026-05-17.

- Review folder: `output/translation_fill_2026-05-17/`
- Combined translations: `output/translation_fill_2026-05-17/all_translations.json`
- Apply summary: `output/translation_fill_2026-05-17/apply_summary.json`
- Backup before apply: `output/translation_fill_2026-05-17/n2vocab.sqlite.before_translation_fill_20260517_124125.bak`
- Rows translated/applied: `1133`
- Post-apply validation: `PRAGMA integrity_check` returned `ok`
- Post-apply missing counts for N2: English `0`, Chinese `0`

One API request timed out during generation at batch 19. The script was patched to catch raw Python `TimeoutError`, then resumed from the already-written batch files.

The SQLite file on the Windows-mounted path also had a non-empty WAL sidecar before apply. It was checkpointed with Windows Python, truncated, and the DB journal mode was set back to `DELETE` so normal WSL reads work again.
