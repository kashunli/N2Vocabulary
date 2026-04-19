# Output Folder Guide

This folder mixes final deliverables, active audio-alignment working files, and optional caches.
The names are stable because several scripts write to hardcoded paths, so the cleanup here favors
clarity over aggressive moving/renaming.

## Keep First

These are the main project outputs.

- `vocabulary_combined.json`
  - master combined vocabulary extracted from the book
- `vocabulary_db.json`
  - clean working database used for clips, explanations, dashboard, and deck builds
- `N2Words.apkg`
  - main word-centered Anki deck
- `N2Words_listening.apkg`
  - listening deck
- `clips/`
  - actual word and sentence audio clips used by the project

## Current Audio-Mapping Work

These are the important files for the current GPT piece-mapping workflow.

- `unit1_entries/`, `unit2_entries/`, `unit3_entries/`
  - per-track expected entry lists fed into `align_track_by_llm.py`
- `unit1_mappings/`, `unit2_mappings/`, `unit3_mappings/`
  - GPT-produced mapping JSON files with timing choices
- `review_unit1_*.json`, `review_unit2_*.json`, `review_unit3_*.json`
  - applied cut results per track
- `review_unit1_combined.json`, `review_unit2_all.json`, `review_unit3_all.json`
  - combined review files for each unit

## Audits And Verification

These are useful for checking clip quality, but they are not the source of truth.

- `unit1_clip_audit.json`, `unit1_clip_audit_suspect.json`, `unit1_clip_audit.md`
- `unit2_clip_audit.json`, `unit2_clip_audit_suspect.json`, `unit2_clip_audit.md`
- `track09_clip_audit.*`, `track10_clip_audit.*`
  - temporary focused audits for recent Unit 2 repair work

If a file name ends in `_suspect.json`, it is just the filtered problem list from the matching audit.

## Caches

These are optional speed/support files. They can usually be regenerated.

- `whisper_cache/`
  - full-track Whisper / whisper.cpp caches, transcripts, and manifests
- `unit01_clip_transcript_cache_whisper_cpp_large_v3_turbo.json`
- `unit02_clip_transcript_cache_whisper_cpp_large-v3-turbo.json`
- `unit02_clip_transcript_cache_whisper_cpp_large-v3-turbo_post_recut.json`
- `track09_clip_transcript_cache.json`
- `track10_clip_transcript_cache.json`

You generally keep these if you expect to continue audit or repair work soon.

## Explanation Batch Files

These are intermediate explanation-generation artifacts.

- `explanations_unit*_all.json`
- `explanations_unit04_chunk2.json`
- `explanations_unit04_chunk3.json`

They are useful historical inputs, but the merged result that matters most is already in `vocabulary_db.json`.

## Data Dumps

These are mostly helper exports used during explanation or review workflows.

- `unit1_data.txt`
- `unit2_data.txt`
- `unit4_data.txt`
- `unit4_chunk1_data.txt`
- `unit4_chunk2_data.txt`
- `unit4_chunk3_data.txt`
- `unit5_data.txt` through `unit13_data.txt`

They are low-risk helper artifacts, not core pipeline state.

## HTML

- `html/`
  - generated HTML pages and dashboards

## Backup

- `vocabulary_db.json.bak`
  - one local backup copy of the DB

Keep this unless you intentionally want fewer safety nets.

## Ignore

- `whisper_tmp/`
  - scratch directory for whisper.cpp temporary work
  - not a source of truth
  - currently contains a few stale Windows ACL-broken temp directories that could not be removed from this session

If future runs behave normally, this folder should stay small or get recreated as needed.

## One Important Note About `-deduced` Clips

Some files inside `clips/` still end with `-deduced.mp3`.
Those are not random leftovers right now: many are still referenced by `vocabulary_db.json`.

So:

- do not bulk-delete `clips/*/*-deduced.mp3` unless you also rebuild or migrate the DB references

## Quick Mental Model

If you only care about the current usable outputs, look at:

- `vocabulary_db.json`
- `N2Words.apkg`
- `N2Words_listening.apkg`
- `clips/`
- `unit2_mappings/`
- `review_unit2_all.json`
- `unit2_clip_audit.*`

Everything else is support material, cache, or historical workflow output.
