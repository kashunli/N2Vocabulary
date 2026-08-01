# Visible-scope consecutive audio playback

Date: 2026-07-14

## Why

Card study needed one continuous-play control that follows the learner's current view instead of requiring a click on every word and sentence.

## What changed

- Added a `play visible` control to the card-study toolbar.
- The queue snapshots `state.currentEntries`, so it follows the active book, section, known/flagged/unmarked filter, and search result exactly.
- Each visible card plays its word audio and then its main example-sentence audio before advancing.
- Missing word or main-sentence clips are prepared through the existing per-entry audio endpoints.
- While running, the same control becomes `stop` and shows word-level progress.
- Changing the visible scope cancels the old queue before new cards render.
- Manual word/sentence playback also stops the continuous queue, leaving only one active audio element.

## Verification

- `node --check` passed for every file under `wordService/static/js/`.
- `cargo fmt --check` passed.
- `cargo test` passed all 23 Rust and repository tests.
- A throwaway-port browser smoke showed one enabled play control for 100 visible cards, then 18 visible cards after selecting the Flagged filter.
- The first word and main-sentence media URLs both returned HTTP 200, and the page reported no browser console warnings or errors.

## Next step

The selected visual direction is now implemented:

- The active card receives a warm paper wash, navy progress line, and compact `Now playing` label.
- Word playback accents the headword; sentence playback accents the main sentence in pale blue.
- Existing red flagged and green known meanings remain intact.
- The queue follows off-screen cards into view, respecting reduced-motion preferences.
- A deterministic `?playback-preview=word|sentence` state supports future visual regression checks without starting audio.
- `wordService/design-qa.md` records the source mock, browser captures, comparison history, interaction checks, and passing result.

## 2026-07-18 pause, resume, and start-here extension

- The toolbar control now has explicit `playing`, `paused`, and `idle` states.
- Pausing keeps the current `Audio` object alive, so resume continues from the
  same clip timestamp instead of replaying the word or sentence.
- The paused card keeps its progress line and changes its label to `Paused`.
- Clicking any card while the visible queue is playing or paused restarts at
  that card's word, then continues with its main sentence and later cards.
- Card buttons keep their existing actions, while keyboard activation of card
  audio text follows the same start-here behavior as a card click.
- Active playback gives other cards a small `Start here` hover hint.
- Book, section, mark-filter, search, and view changes still discard the old
  queue rather than resuming against a different visible list.

### Extension verification

- `node --check` passed for the changed JavaScript modules.
- `git diff --check`, `cargo fmt --check`, and all 24 Rust/repository tests passed.
- A deterministic Playwright smoke verified that pause retained
  `currentTime = 1.25`, resume reused the same audio object, and clicking card
  3 changed the active queue/card from position 1 to position 3.
