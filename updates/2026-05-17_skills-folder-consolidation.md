# 2026-05-17 - Skills Folder Consolidation

The project root had several current or reusable skill folders mixed with source data and generated outputs. To prepare for reviewing the skills one by one, the active/reusable skill assets were gathered under `skills/`.

Moved into `skills/`:

- `cutTwice/`
- `makeAnkiCards/`
- `batch-japanese-sentence-explanations/`
- `japanese-sentence-explanation-skill/`
- `japanese-sentence-explanation.skill`

Updated docs and command examples to use the new paths. The Anki scripts now resolve the repository root from their deeper location under `skills/makeAnkiCards/scripts/`.

Generated Python cache folders were removed from the moved skill area and nearby workflow folders.
