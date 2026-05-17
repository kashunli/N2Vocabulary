# Decisions

## 2026-04-25: Use One Root Git Repository

`parse/` used to have its own Git repository. Its history was preserved as `legacy/git-history/parse-main-2026-04-25.bundle`, then `parse/` was flattened so the root repository can track parser docs and project files directly.

Reason: one repo is easier for this personal pipeline and much easier for AI agents to understand.

## 2026-04-25: Keep cutTwice as Current Audio Workflow

`skills/cutTwice/` is the current audio-cutting workflow. It reads source tracks from `audio/` and writes durable clips to root `clips/`.

Reason: the pair-first workflow with `pairs.json` gives a compact repair artifact and avoids hiding important decisions in old mapping scripts.

## 2026-04-25: Treat output/ as Compatibility, Not Ideal Architecture

`output/` currently remains because older paths and artifacts still refer to it. The target mental model is `dist/` for final products, `work/` for audit/review/mapping artifacts, and `cache/` for disposable ASR or temp files.

Reason: physical renames should happen after hardcoded legacy paths are retired, but the conceptual split should guide new work immediately.

## 2026-04-25: Keep Reflections Out of Operational Context

Use `updates/` for dated narrative history, `docs/DECISIONS.md` for durable choices, and `CLAUDE.md` for short agent-facing operating rules.

Reason: preserving reflection is valuable, but long history inside agent context makes future work slower and more confusing.

## 2026-04-25: Design for AI-Operated Workflows

This repository is usually operated by asking an AI agent to run and maintain workflows, not by manually remembering commands. Prefer small concrete skill folders over loose scripts:

- each recurring workflow gets one folder with `SKILL.md`
- scripts live beside the skill that uses them
- `SKILL.md` states inputs, outputs, cache/work folders, validation, and known traps
- split large workflows into smaller skills instead of one giant skill
- keep agent-facing context short and current; put narrative history in `updates/`

Reason: future AI agents need fast orientation and explicit contracts more than a human-oriented pile of scripts.

## 2026-05-17: Gather Current Skills Under skills/

Current and reusable workflow skills live under `skills/` so they can be reviewed one by one without mixing them into source data, generated outputs, or old reference code.

Reason: `cutTwice`, `makeAnkiCards`, and the Japanese explanation skills are reusable workflow assets. Keeping them in one place makes future review and cleanup easier while leaving `legacy/` reserved for older reference approaches.
