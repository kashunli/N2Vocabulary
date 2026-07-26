# Project Memory for AI Agents

This repository is maintained as an AI-operated learning/workflow project. Future agents should optimize for safe continuation with limited context, while keeping the code readable enough for the user to learn from it.

## AI-Maintainable Workflow Principles

Goal: optimize the project so a future AI assistant and the user can safely understand, modify, verify, rerun, and resume work with limited context.

1. Prefer local clarity over premature abstraction. Slight repetition is acceptable when it keeps inputs, outputs, assumptions, and workflow boundaries visible in one place.
2. Keep workflow-specific code and helpers near the workflow folder. Promote shared helpers only when the contract is stable across multiple workflows.
3. Make every workflow runnable from one obvious entrypoint, with cheap validation commands for important outputs.
4. Keep source, working, generated, archived, cache, review, and authoritative files clearly separated and documented. 
5. Add validation at workflow boundaries, especially before overwriting files, merging JSON, renaming clips, or building Anki packages.
6. Use comments to explain non-obvious data assumptions, numbering rules, resume behavior, and human review points. Avoid comments that merely restate code.
7. Prefer structured logs and resume notes that another agent can parse: what ran, what succeeded, what failed, and what should happen next.
8. Keep public entrypoints, data schemas, manifests, and final outputs human-readable and easy to audit, even when internal implementation favors context locality over excessive DRY.
9. Periodically promote stable workflows into cleaner shipped packages.

## Teaching-Oriented Maintenance

- Write code that teaches as well as works: add helpful comments for non-obvious logic, workflow boundaries, and data assumptions.
- Keep comments useful and concrete; avoid comments that only restate a line of code.
- When using terminal, Linux, or Git commands for the user, briefly explain what each command is for.

## Commit Discipline

- After every bugfix, feature update, or forward step — commit to git with a short, specific message describing what changed and why.
- Commit messages should name the affected subsystem or file area (e.g. "wordService playback", "cutTwice threshold", "db migration").
- End each commit message with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

## Local Workflow Shape

- Prefer small, self-contained workflow folders with a `SKILL.md`, nearby scripts, and clear input/output/cache contracts.
- Keep workflow-specific helpers near the workflow even if that means a little duplication.
- Promote shared helpers only when they represent stable project contracts or genuinely common infrastructure.
