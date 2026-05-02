# Scripts Agent Notes

## Test Rendering Direction

`json_to_test.js` is already too large. Do not keep adding instruction-string guesses to it.

The exercise rendering pipeline should be tag-first:

1. Analyze test JSON sections and write an explicit `render_type` on each exercise block.
2. Render from `render_type` only. Missing or unknown tags should degrade to `raw_text`, which keeps source content visible but does not create interactive answer controls.
3. Put new classification rules in `render_type_rules.js`.
4. Use `tag_test_render_types.js` to apply tags to JSON before regenerating HTML.
5. Keep `json_to_test.js` as a thin CLI entry point only.

## File Map

- `json_to_test.js`: command-line parsing and file generation orchestration.
- `test_page_builder.js`: main `render_type` dispatch and JSON-to-HTML section renderers.
- `test_page_assets.js`: large CSS strings and shared browser runtime loading; rarely edited.
- `test_guide_page.js`: generated exercise index page; rarely edited.
- `render_type_rules.js`: JSON analysis and render-type classification.
- `tag_test_render_types.js`: CLI for applying `render_type` tags to JSON.

## Current Commands

From `wordsAndExerciseInHtml/`:

```powershell
node scripts\tag_test_render_types.js exercise_json\n2
node scripts\tag_test_render_types.js exercise_json\n2 --write
node scripts\json_to_test.js generate-folder exercise_json\n2 --out-root exercises\n2 --build-index
```

Before running the tagger with `--write`, back up `exercise_json/n2`.

## Render Types In Use

Common tags:

- `checkbox`: word list with checkboxes
- `single_choice`: one-answer option pills
- `letter_choice`: a/b/c/d option pills
- `synonym_choice`: closest-meaning a/b/c/d questions
- `usage_choice`: usage-choice a/b/c/d questions
- `write_in`: typed answer input
- `particle_fill`: particle blanks
- `token_fill`: click-to-fill from a word bank
- `editable_token`: click-to-fill then modify the form
- `multi_select`: multiple option pills
- `table`: table completion
- `raw_text`: source is too malformed or unstructured for an interactive renderer

## Near-Term Plan

- Keep `json_to_test.js` stable except for CLI and generation-flow fixes.
- Put renderer dispatch changes in `test_page_builder.js`.
- Move future classification edits into `render_type_rules.js`.
- When a JSON section renders poorly, fix its `render_type` or structure first, then regenerate.
- Later, split renderers out of `test_page_builder.js` by type, one file at a time.
