# 2026-04-25 — Directory reorganization

## Context

The project root had accumulated ~260 MB of mixed state: untracked scripts at the root, stale `.bk` backups, regenerable caches, and ~100 intermediate per-unit alignment artifacts scattered across `output/`. Goal: make `cutTwice/` the obvious entry point, archive earlier code as a reference library (not delete — user wants to mine it when authoring new skills), and group `output/` by purpose.

User decisions that shaped the plan:
- `cutTwice/` is the CURRENT canonical audio-cutting pipeline.
- `align_track_by_llm.py`, `align/`, `full-unit-cutter/`, `gpt-track-piece-mapper/`, and `parse/scripts/` are LEGACY → archive, don't delete.
- `oldClips/` + `.bk` backups → preserve under `legacy/`.
- Prune regenerable caches; update `.gitignore` to prevent recurrence.
- Authoring preference: self-contained skills (markdown + scripts bundled) over loose script folders.

## Target structure

```
N2Vocabulary/
├── cutTwice/                    ← CURRENT pipeline
├── audio/ json/ clips/ tools/   ← unchanged
├── output/
│   ├── vocabulary_combined.json
│   ├── vocabulary_missing_restored.json
│   ├── alignment/
│   │   ├── review/              ← review_unit*_track_*.json
│   │   ├── entries/             ← unit{1..7}_entries/ + unit5_entries_repair/
│   │   ├── mappings/            ← unit{1..7}_mappings/
│   │   └── audits/              ← track*_clip_audit*, unit*_clip_audit*, *_transcript_cache*
│   ├── explanations/
│   │   ├── explanations_unit*.json
│   │   └── batches/             ← unit*_data.txt dumps
│   ├── N2Words.apkg, N2Words_listening.apkg
│   └── README.md, missing_audio_entries.md
├── legacy/
│   ├── README.md                ← explains archive intent
│   ├── scripts/                 ← align_track_by_llm.py, align/, cut_units1to6.sh, __init__.py
│   ├── skills/                  ← full-unit-cutter, gpt-track-piece-mapper
│   ├── parse-scripts/           ← entire former parse/scripts/ tree
│   ├── backups/                 ← vocabulary_combined.json.bk, vocabulary_db.json.bk
│   └── oldClips/                ← 80 MB pre-recut audio archive (gitignored)
├── parse/
│   ├── N2語彙トレーニング.pdf
│   ├── structured/
│   └── pages_8_15_schema/
├── dashboard.html, RESUME.md, CLAUDE.md
└── updates/                     ← this folder (amelioration records)
```

## Actions performed

1. **Created** `legacy/{scripts,skills,parse-scripts,backups,oldClips}/` and `output/alignment/{review,entries,mappings,audits}/`, `output/explanations/batches/`.
2. **Moved to `legacy/scripts/`**: `align_track_by_llm.py`, `align/`, `cut_units1to6.sh`, `__init__.py`.
3. **Moved to `legacy/skills/`**: `full-unit-cutter/`, `gpt-track-piece-mapper/`.
4. **Moved `parse/scripts/` → `legacy/parse-scripts/`** (entire former Python pipeline — parse_book.py, make_anki.py, make_anki_listening.py, make_html.py, make_clean_db.py, merge_explanations.py, dump_explanation_batch.py, audit_unit_clips.py, cache_track_transcripts.py, suggest_local_repair.py, merge_assigned_clips.py, pipeline/, etc.).
5. **Moved to `legacy/backups/`**: `vocabulary_combined.json.bk`, `vocabulary_db.json.bk`.
6. **Moved to `legacy/oldClips/`**: 80 MB pre-recut clip archive.
7. **Reorganized `output/`**:
   - `review_unit*.json` → `alignment/review/`
   - `unit{1..7}_entries/`, `unit5_entries_repair/` → `alignment/entries/`
   - `unit{1..7}_mappings/` → `alignment/mappings/`
   - `track*_clip_audit*`, `unit*_clip_audit*`, `*_transcript_cache*`, `unit5_{489_508,509_510}_audit*` → `alignment/audits/`
   - `explanations_unit*.json` → `explanations/`
   - `unit*_data.txt` → `explanations/batches/`
8. **Deleted**: `output/whisper_cache/`, `output/repair_debug/`, `output/piece29_16k.*` (test artifact).
9. **Left in place**: `output/whisper_tmp/wcpp_*` — 6 subfolders held permission locks (likely from a prior whisper.cpp process); now gitignored so they don't clutter `git status`.
10. **Updated `.gitignore`** — added `output/whisper_cache/`, `output/whisper_tmp/`, `output/repair_debug/`, `output/alignment/audits/*_clip_transcript_cache*`, `*.bk`, `*.bak`, `legacy/oldClips/`.
11. **Wrote `legacy/README.md`** — explains the archive is a reference library for mining patterns when building new skills, not for direct invocation.
12. **Rewrote `CLAUDE.md`** — `cutTwice/` promoted as primary pipeline; legacy section points at `legacy/README.md`; working-conventions section captures the skill-first authoring preference.

## Verification

- `git status` — modifications are all renames / deletes of intermediate files. No unintended edits to tracked source.
- `du -sh legacy output` — 83 MB / 154 MB; no duplication.
- Root `ls` — reduced to the expected working dirs + legacy + updates.

## Not touched (out of scope this round)

Other root folders found but not triaged: `explore/`, `japanese-sentence-explanation-skill/`, `makeAnkiCards/`, `node_modules/`, `ocrAndFix/`, `wordsAndExerciseInHtml/`. Flag for a future cleanup pass if any are stale.

## Known residue

- `output/whisper_tmp/wcpp_*` — permission-locked subfolders. Can be deleted after rebooting / ensuring no whisper.cpp process holds them.
- `parse/` retains `docs/`, `README.md`, `unit2_track_config.json`; `structured/` and `pages_8_15_schema/` (referenced in CLAUDE.md) were not present on disk at reorganization time — worth verifying.

## Source plan

Original plan file (kept for reference): `C:\Users\lochl\.claude\plans\this-folder-is-quite-curious-gizmo.md`.
