# Design QA - Study Wall stepped three-card playback window

## Compared state

- Source visual truth: tmp/source-study-wall-mock.png (approved Study Wall mock supplied by the user).
- Implementation screenshot: tmp/study-wall-three-card-window-solid-tags-1487x1058.png.
- Viewport: 1487 x 1058 CSS pixels.
- State: Flagged scope, tenth card (履歴), paused, 10 of 18; Known was temporarily enabled for the screenshot and restored afterward.
- Intentional state difference: the source mock shows sentence playback with deferred pause copy; the accepted product behavior now shows immediate Paused / Resume copy.

## Full-view comparison evidence

The implementation preserves the established Study Wall styling while making the playback sequence spatially explicit: previously played card on the left, enlarged current card in the center, and next-to-play card on the right. The matched desktop viewport has no horizontal overflow and the dock remains fully visible.

## Focused-region comparison evidence

The three playback roles and active-card mark controls are readable at full-view resolution, so a separate crop was not needed. Flagged settles to rgb(220, 38, 38) and Known settles to rgb(22, 163, 74), both with white text and matching borders. The screenshot visibly confirms the full red and green tag fills.

## Required fidelity surfaces

- Fonts and typography: unchanged; the enlarged current card continues to use the existing hierarchy and keycap styles.
- Spacing and layout rhythm: desktop uses left/current/right columns; tablet uses previous and next in column one with current in column two; mobile stacks previous/current/next in one column.
- Colors and visual tokens: active Flagged and Known tags use the existing semantic red and green as full fills with white content.
- Image quality and asset fidelity: no raster or custom image assets were added or replaced.
- Copy and content: playback and shortcut copy remains unchanged by the moving-window update.

## Interaction verification

- With Next retaining focus, pressing Space paused playback at card 2 while focus remained on Next; the focused Next control did not activate.
- With Next retaining focus and playback paused at 2 / 18, pressing Enter changed the active card from known=false to known=true without moving playback. A second Enter restored known=false, leaving persisted study data unchanged.
- From paused position 2, D moved to 3 and an immediate Space paused there; A returned to 2 and paused there.
- The capture-phase shortcut handler prevents focused controls from receiving Space or Enter outside text entry.
- Form fields remain exempt so normal typing still works.
- At position 9 of 18 the window roles were previous=44, current=57, next=63. Advancing once produced previous=57, current=63, next=64 and moved scrollY from 1254 to 1316, a 62-pixel forward step.
- At 1487 px the three roles occupy distinct left, center, and right columns with no horizontal overflow.
- At 900 px the current card occupies column two while previous and next share column one; horizontal overflow is zero.
- At 390 px previous, current, and next stack in order in one column; horizontal overflow is zero.
- Known was toggled only to verify its solid fill, then restored to aria-pressed=false and its inactive background.
- Browser console: no warnings or errors.

## Comparison history

- The approved source and implementation were emitted together for direct visual comparison at 1487 x 1058.
- The moving window retains the accepted card, transport, and semantic-mark design language.
- No P0, P1, or P2 visual findings were introduced by the playback-window changes.

## Findings

- No remaining P0, P1, or P2 issues.
- P3 follow-up: none required.

final result: passed

## Targeted follow-up - RepeatOnce, editable pause, and study spacing

### Source visual truth

- Pause-control reference: `C:/Users/lochl/AppData/Local/Temp/codex-clipboard-27e4bd2a-51b8-47cb-8787-c8b2ab5461dd.png` (1539 x 233 px).
- Selected RepeatOnce reference: `C:/Users/lochl/AppData/Local/Temp/codex-clipboard-975eb552-49c7-4aea-999b-6f87c56b3df3.png` (300 x 267 px).
- Spacing references: `C:/Users/lochl/AppData/Local/Temp/codex-clipboard-af278041-329c-4977-a1b7-74bea2be3ffb.png` (1119 x 258 px) and `C:/Users/lochl/AppData/Local/Temp/codex-clipboard-45dea117-d383-42f1-ac69-12aebb8af6e3.png` (1083 x 207 px).

### Implementation evidence

- Single-mode toolbar: `C:/Users/lochl/.codex/visualizations/2026/08/29/01a04bb2-4a29-7380-af77-728190d832d7/n2vocab-single-mode.png` (1280 x 900 px, CSS viewport 1280 x 900, density 1).
- Playback settings before manual edit: `C:/Users/lochl/.codex/visualizations/2026/08/29/01a04bb2-4a29-7380-af77-728190d832d7/n2vocab-playback-settings.png` (1280 x 900 px, CSS viewport 1280 x 900, density 1).
- Playback settings after typing `4.2`: `C:/Users/lochl/.codex/visualizations/2026/08/29/01a04bb2-4a29-7380-af77-728190d832d7/n2vocab-playback-settings-edited.png` (1280 x 900 px, CSS viewport 1280 x 900, density 1).
- Study-wall spacing after adjustment: `C:/Users/lochl/.codex/visualizations/2026/08/29/01a04bb2-4a29-7380-af77-728190d832d7/n2vocab-spacing-after.png` (1280 x 900 px, CSS viewport 1280 x 900, density 1).

### State and comparison evidence

- Loaded N2 study wall, All sections, vocabulary list visible, Single audio mode selected.
- The toolbar uses the selected `RepeatOnce` icon from the existing Phosphor icon package.
- The settings modal shows a keyboard-editable pause value beside a 0–5 second slider.
- The typed interaction assertion changed the pause field from `0.5` to `4.2`; after blur, both the field and slider reported `4.2`.
- The current-word content begins higher after reducing the content/current top padding, and the sentence explanation begins closer after reducing its top margin from `22px` to `10px`.

### Required fidelity surfaces

- Fonts and typography: existing product fonts, weights, and sizes are unchanged; the editable pause value keeps the existing monospace numeric treatment.
- Spacing and layout rhythm: the two requested vertical gaps are reduced without changing the word, sentence, translation, or explanation content.
- Colors and visual tokens: existing paper, indigo, line, and focus tokens remain in use.
- Image quality and asset fidelity: no new raster assets or custom icon drawings were added; `RepeatOnce` is rendered from the installed icon library.
- Copy and content: existing learner-facing copy is unchanged.

### Comparison history

- Earlier pass: the selected RepeatOnce icon and editable pause control were captured in the single-mode and settings screenshots above.
- Follow-up pass: the two spacing adjustments were applied, rebuilt, and captured in `n2vocab-spacing-after.png`; no P0, P1, or P2 differences remain in the requested regions.

### Findings

- No remaining P0, P1, or P2 issues in the requested icon, pause-control, or study-content spacing regions.
- P3 follow-up: none required.

final result: passed
