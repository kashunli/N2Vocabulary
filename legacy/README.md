# legacy/

Reference code archive. Not for direct invocation.

`skills/cutTwice/` at the project root is the current audio-cutting pipeline. Everything under this folder was part of an earlier approach and is kept as reference material — patterns and snippets to mine when authoring new skills, not working code.

## Contents

- `scripts/` — root-level alignment scripts that preceded `skills/cutTwice/`:
  - `align_track_by_llm.py` — Whisper + LLM track aligner
  - `align/` — support module (artifacts, boundaries, cut, prompt, etc.)
  - `cut_units1to6.sh` — batch runner for Units 1–6
  - `__init__.py` — stray package marker
- `skills/` — earlier Claude Code skill definitions:
  - `full-unit-cutter/`
  - `gpt-track-piece-mapper/`
- `parse-scripts/` — former `parse/scripts/` Python pipeline (OCR → JSON → audio alignment → Anki):
  - Key scripts worth studying: `parse_book.py`, `make_anki.py`, `make_anki_listening.py`, `make_html.py`, `make_clean_db.py`, `merge_explanations.py`, `dump_explanation_batch.py`
  - Alignment utilities: `align_track_by_llm.py`, `audit_unit_clips.py`, `cache_track_transcripts.py`, `suggest_local_repair.py`, `merge_assigned_clips.py`
  - `pipeline/` subpackage: `audio.py`, `align.py`, `vocab.py`, `text.py`, `output.py`, `models.py`
- `backups/` — point-in-time snapshots of the master DB:
  - `vocabulary_combined.json.bk` (2026-04-14)
  - `vocabulary_db.json.bk` (2026-04-20)
- `oldClips/` — 80 MB of pre-recut audio clips. Superseded by `clips/` at the project root. Gitignored.

## When to look here

- Building a new skill that needs to do alignment, Anki deck generation, OCR parsing, or audit-style re-transcription → crib from `parse-scripts/` and `scripts/`.
- Needing to roll back vocabulary DB state → `backups/`.
- Debugging a clip-level regression → compare against `oldClips/`.
