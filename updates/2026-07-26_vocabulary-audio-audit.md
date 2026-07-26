# Vocabulary/audio agreement audit

## Why

N2 #1118 exposed a parsed-text error: the canonical sentence contained
`訪めかけ`, but both the raw OCR text and the human recording say `詰めかけ`.
This is the kind of one-word substitution that can look superficially similar
enough to escape a broad OCR cleanup.

## Workflow added

`skills/auditVocabularyAudio/` audits every canonical N2 headword and
`main_sentence` against its human clip with a locally cached faster-whisper
model. It keeps an input-signed transcript cache, uses phonetic comparison to
reduce false positives from ASR kanji choices, and emits a ranked review queue.

The script opens SQLite in read-only mode and never applies ASR output back to
the database. Corrections remain a separate human-reviewed repair step.

## Commands

```powershell
python -m unittest discover skills/auditVocabularyAudio/tests -v
python skills/auditVocabularyAudio/scripts/audit_vocabulary_audio.py --preflight
python skills/auditVocabularyAudio/scripts/audit_vocabulary_audio.py --unit 13
python skills/auditVocabularyAudio/scripts/audit_vocabulary_audio.py
```

The default ASR configuration is local/offline `faster-whisper small` on CPU
with `int8`. Generated caches live under `cache/`; audit artifacts live under
`work/vocabulary_audio_audit/`.


## Completed N2 baseline

The complete audit ran with the local Vulkan `whisper.cpp` large-v3-turbo
model:

- 1,160 canonical N2 placements
- 2,320 human word/main-sentence clips
- 0 missing clips
- 978 entries passed both thresholds
- 182 entries entered review (199 individual comparisons: 120 words and 79
  sentences)

Raw-OCR corroboration could locate source blocks for 65 of the 79 reviewed
sentences. It classified 32 as conservative source-confirmed correction
candidates, 27 as cases where raw OCR supports the database, and 6 as
ambiguous. Generated review artifacts are local under
`work/vocabulary_audio_audit/n2_all_both/`; the transcript cache is resumable
under `cache/vocabulary_audio_audit/`.
