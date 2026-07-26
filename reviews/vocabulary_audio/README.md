# Vocabulary audio reviews

This folder contains authoritative human decisions exported from the offline audio
review page and checked against the signed audit evidence.

- `n2_all_both.json` is the current N2 review result.
- `validation.status` is `valid_complete` only when every evidence row has a
  decision; `valid_incomplete` lists remaining source indices.
- `audio_problem` means the text should remain unchanged but the sentence clip
  needs repair or replacement.
- These files do not update SQLite. Apply accepted text changes through a
  separate validated data-repair workflow.

Regenerate a checked result with
`skills/auditVocabularyAudio/scripts/validate_review_decisions.py`.
