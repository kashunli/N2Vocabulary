# Vocabulary audio reviews

This folder contains authoritative human decisions exported from the offline audio
review page and checked against the signed audit evidence.

- `n2_all_both.json` is the current N2 review result.
- `n2_all_both_candidates.json` is the signed, non-authoritative evidence
  bundle served by wordService at `/audio-review.html`. The browser stores
  live decisions in `wordService/data/audio_reviews.sqlite`.
- `validation.status` is `valid_complete` only when every evidence row has a
  decision; `valid_incomplete` lists remaining source indices.
- `audio_problem` means the text should remain unchanged but the sentence clip
  needs repair or replacement.
- These files do not update SQLite. Apply accepted text changes through a
  separate validated data-repair workflow.

Regenerate both checked artifacts with:

```powershell
python skills/auditVocabularyAudio/scripts/validate_review_decisions.py C:\path\to\review.json `
  --candidate-output reviews/vocabulary_audio/n2_all_both_candidates.json
```

The candidate bundle is evidence only. Export and validate the service's live
decisions before treating them as authoritative.
