# 2026-08-13 - Luna English audio-cutting guide

## Why

Preserve the successful N1 word/example-sentence cutting experience as a
reusable, model-facing workflow for English-learning recordings of the same
shape.

## What changed

- Added `docs/LUNA_ENGLISH_AUDIO_CUTTING_GUIDE.md`.
- Documented the two-level pause model: longer gaps separate complete learning
  items, while the first qualifying medium gap inside an item separates the
  word from its example sentence.
- Preserved the N1 calibration evidence and validation results while clearly
  marking its thresholds as source-specific rather than English defaults.
- Defined the division of responsibility between deterministic code and Luna,
  a structured Luna request/response contract, review gates, resumable export,
  final validation, and failure behavior.
- Linked the guide from the audio runbook.

## Validation

- Checked the guide against the accepted N1 alignment decisions, completed
  workflow notes, audit report, and exporter/validator contracts in the source
  `minikaraWordN1` project.
- Verified that all repository links and example JSON blocks are structurally
  readable.
- Ran `git diff --check` before committing.

## Residual risk

The N1 silence thresholds describe one Japanese studio recording and are only
initial calibration candidates for English. A representative English pilot and
listening review remain mandatory before bulk export.
