# updates/

Amelioration records — one file per significant reorganization, refactor, or structural change to this project. Each entry captures **why**, **what was done**, and **anything left residual**, so future sessions can recover the reasoning without digging through git log.

Naming: `YYYY-MM-DD_short-slug.md`.

## Index

- [2026-05-17 - Skills folder consolidation](2026-05-17_skills-folder-consolidation.md) - gathered active/reusable skill workflows under `skills/` for later one-by-one review.
- [2026-05-17 - SQLite translation fill](2026-05-17_sqlite-translation-fill.md) - prepared the one-time Aliyun/DeepSeek translation-fill job for blank `meaning_en` and `meaning_zh` fields in `output/n2vocab.sqlite`.
- [2026-05-17 - Entry example sentence normalization](2026-05-17_entry-examples-sentence-translation.md) - moved main sentences into `entry_examples.position = 0`, added example translations/audio/explanation metadata, and filled English/Chinese example translations.
- [2026-04-25 — Directory reorganization](2026-04-25_directory-reorganization.md) — archived legacy scripts/skills to `legacy/`, grouped `output/` artifacts into `alignment/` + `explanations/`, promoted `cutTwice/` as the canonical pipeline.
