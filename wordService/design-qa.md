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
