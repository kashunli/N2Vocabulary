# Autoplay review transport

## Why

The study flow should push the learner forward through the current visible list. Review actions are optional interventions, not a required self-rating step.

## What changed

- Added a persistent Study Wall transport with start, replay, previous, immediate pause, next, stop, progress, and visible keyboard hints.
- Made pause and replay immediate so the learner always controls the current audio directly.
- Added `R` replay, `F` flag, `Enter` / `K` known, `A` / Left Arrow previous, and `D` / Right Arrow next shortcuts.
- Reserved Space and Enter for study actions outside text entry, even when a visible control retains focus.
- Added a stepped playback window that keeps the previous card left, current card enlarged in the center, and next card right, with responsive tablet and mobile layouts.
- Filled active Flagged and Known controls with their full semantic red and green colors.
- Kept the queue tied to a snapshot of the loaded book, section, state filter, and search result; playback is disabled while a new scope is loading.

## Verification

- JavaScript syntax and whitespace checks passed.
- Rust tests passed.
- Browser checks verified immediate pause/replay, reserved Space/Enter behavior, A/D navigation, solid mark colors, and one forward scroll step per card transition.
- Desktop, 900 px tablet, and 390 px mobile layouts were checked with no horizontal overflow or console errors.
