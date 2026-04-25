# 2026-04-25 — Flatten parse and clarify workflow layout

## Actions

- Preserved the nested `parse/` repository history as `legacy/git-history/parse-main-2026-04-25.bundle`.
- Flattened `parse/` into the root repository by removing the nested `.git` directory after history preservation.
- Added root `README.md`.
- Added compact current docs:
  - `docs/ARCHITECTURE.md`
  - `docs/RUNBOOK.md`
  - `docs/DECISIONS.md`
- Updated `CLAUDE.md` to point future agents at the current docs and folder contract.
- Updated `cutTwice/SKILL.md` with the current input/output/cache conventions.
- Added `makeAnkiCards/SKILL.md` as the small AI-facing entry point for future Anki promotion work.
- Rewrote `output/README.md` to describe `output/` as a compatibility bucket.

## Design note

Skills should own an explicit file contract, not the entire project layout. For this repo, `cutTwice` reads from `audio/`, writes durable clips and `pairs.json` under root `clips/`, and leaves broader review/cache artifacts to `work/`/`cache/` in the target layout or `output/alignment/` during compatibility cleanup.

The user's current AI-coding principle is now recorded in `docs/DECISIONS.md`: keep skills small and concrete, split large skills, and optimize folder clarity for AI agents because the user usually asks AI to operate the workflows rather than running scripts manually.
