# updates/

Amelioration records — one file per significant reorganization, refactor, or structural change to this project. Each entry captures **why**, **what was done**, and **anything left residual**, so future sessions can recover the reasoning without digging through git log.

Naming: `YYYY-MM-DD_short-slug.md`.

## Index

- [2026-06-28 - All-book Anki exports](2026-06-28_anki-all-books-export.md) - rebuilt every book's word-card APKG and fixed kana-only Green Word Book rows that otherwise produced notes without cards.
- [2026-06-25 - N2_1500 related forms as examples](2026-06-25_n2-1500-related-forms-examples.md) - moved related forms out of explanations into categorized `entry_examples` rows with preserved readings.
- [2026-06-25 - N2_1500 English meanings](2026-06-25_n2-1500-english-meanings.md) - populated English word meanings for the imported N2_1500 book.
- [2026-06-25 - Word-card group exports](2026-06-25_word-card-group-exports.md) - made the word-card front headword-only and added SQLite-backed group export filters.
- [2026-06-22 - N2 must-1500 PDF import](2026-06-22_n2-must-1500-pdf-import.md) - extracted 1,488 text-layer entries into auditable JSON and the existing multi-book SQLite/web service.
- [2026-06-21 - Card audio generation](2026-06-21_card-audio-generation.md) - made a card click ensure and download both word and main-sentence audio through the Rust service.
- [2026-06-19 - GWB duplicate merge](2026-06-19_gwb-duplicate-merge.md) - merged exact GWB duplicates into N2/N3 while preserving source notes, meanings, examples, and progress provenance.
- [2026-05-17 - Skills folder consolidation](2026-05-17_skills-folder-consolidation.md) - gathered active/reusable skill workflows under `skills/` for later one-by-one review.
- [2026-06-03 - Starred sentence review](2026-06-03_starred-sentence-review.md) - added sentence-level stars, all-units starred review, source-word links, and explanation-ready sentence detail.
- [2026-05-17 - SQLite translation fill](2026-05-17_sqlite-translation-fill.md) - prepared the one-time Aliyun/DeepSeek translation-fill job for blank `meaning_en` and `meaning_zh` fields in `output/n2vocab.sqlite`.
- [2026-05-17 - Entry example sentence normalization](2026-05-17_entry-examples-sentence-translation.md) - moved main sentences into `entry_examples.position = 0`, added example translations/audio/explanation metadata, and filled English/Chinese example translations.
- [2026-04-25 — Directory reorganization](2026-04-25_directory-reorganization.md) — archived legacy scripts/skills to `legacy/`, grouped `output/` artifacts into `alignment/` + `explanations/`, promoted `cutTwice/` as the canonical pipeline.
