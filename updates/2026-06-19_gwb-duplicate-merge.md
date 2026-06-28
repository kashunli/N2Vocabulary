# 2026-06-19 - GWB duplicate merge

## Why

Exact GreenWordBook headwords duplicated hundreds of N2/N3 entries. The useful
GWB meanings, metadata, and Chinese-translated examples should enrich the
existing study entry instead of appearing as a second card.

## What changed

- Added `tools/merge_gwb_duplicates.py`, which defaults to a read-only audit
  and requires `--apply` for a backed-up transactional merge.
- Added structured word-note and example-provenance tables through migration
  `003_entry_source_provenance.sql`.
- Preserved destination identity, unit order, readings, audio, explanations,
  marks, and stars. Blank destination fields may be filled, but nonblank fields
  are never replaced by GWB data.
- Appended unique GWB sentences as normal examples and linked exact sentence
  matches to their GWB source instead of duplicating them.
- Extended the Rust detail API and browser modal with labeled GWB meanings,
  notes, and example badges.
- Updated GWB, N2, and N3 import paths to reconcile preserved merged examples
  after future rebuilds.

## Canonical database result

- Matched GWB rows: 924 across 909 exact headwords.
- Destination split: 529 rows to N2 and 395 rows to N3.
- Appended examples: 900; exact sentence matches reused: 3. Two matched
  existing N2 sentences; the third was one sentence repeated by two GWB rows
  for `才能`, retained once with both source links.
- Remaining GWB rows: 3,839.
- Preserved GWB source-note rows: 924.
- Special routing: GWB `何とか` maps to N2 entry 1099.

## Validation

- Python merge/import unit tests.
- Rust repository tests, including source-note and example provenance payloads.
- SQLite foreign-key and integrity checks plus exact post-merge count audits.
