---
name: audit-vocabulary-audio
description: Audit canonical vocabulary headwords and main example sentences against their human audio with local ASR, producing a resumable review queue without automatically changing source text.
---

# Audit Vocabulary Audio

Use this workflow when OCR-derived vocabulary text may disagree with the
corresponding human recording.

## Safety boundary

ASR is evidence, not an editing authority. This workflow never changes the
SQLite database, source JSON, or audio. It writes transcripts and ranked review
artifacts so a human can distinguish an OCR error from an ASR error.

## Inputs

- Canonical database: `wordService/data/n2vocab.sqlite`
- N2 human clips: `clips/words/wordNNN.mp3` and
  `clips/sentences/sentenceNNN.mp3`
- Authoritative main text: `item_examples.kind = 'main_sentence'`

## Entrypoint

Run a cheap database/audio preflight without loading an ASR model:

```powershell
python skills/auditVocabularyAudio/scripts/audit_vocabulary_audio.py --preflight
```

Audit one unit first:

```powershell
python skills/auditVocabularyAudio/scripts/audit_vocabulary_audio.py --unit 13
```

Audit all N2 words and main sentences with the locally cached model:

```powershell
python skills/auditVocabularyAudio/scripts/audit_vocabulary_audio.py
```

Use `--only sentences` when investigating OCR sentence quality, or `--only
words` to check headword clips. `--start-index`, `--end-index`, and `--limit`
provide bounded test runs. Completed transcripts are reused unless the audio
file or ASR configuration changes; `--force` deliberately retranscribes them.

## Local ASR contract

The default backend is `faster-whisper` with the `small` model, Japanese forced
as the language, CPU `int8`, and offline-only model loading. Override the model
with a cached snapshot path if model-name resolution is unavailable:

```powershell
python skills/auditVocabularyAudio/scripts/audit_vocabulary_audio.py `
  --model C:\path\to\faster-whisper-small\snapshot
```

For a full pass on this repository's AMD GPU, reuse the checked-in local
whisper.cpp runtime and its ignored large-turbo model:

```powershell
python skills/auditVocabularyAudio/scripts/audit_vocabulary_audio.py --backend whisper-cpp
```

After a full audit, corroborate sentence candidates against each page JSON's
less-processed `raw_text`. This identifies parsing drift without treating ASR
alone as truth:

```powershell
python skills/auditVocabularyAudio/scripts/triage_source_evidence.py
```

Do not give Whisper the expected word or sentence as a prompt. That would make
the comparison circular and could conceal OCR mistakes.

## Outputs

- `cache/vocabulary_audio_audit/<asr-label>/transcripts.json`: disposable,
  input-signed resume cache.
- `work/vocabulary_audio_audit/<run-label>/audit.json`: complete machine-readable
  audit.
- `work/vocabulary_audio_audit/<run-label>/review_queue.csv`: ranked rows needing
  inspection.
- `work/vocabulary_audio_audit/<run-label>/report.md`: counts, reproducibility
  settings, and the highest-priority mismatches.

Each comparison records surface and phonetic similarity. Phonetic comparison is
primary because correct speech is often written by ASR with different kanji.
Sentence review uses a deliberately strict threshold: a single OCR-corrupted
- `source_evidence.csv`: every reviewed sentence with raw-OCR evidence scores.
- `source_confirmed.md`: conservative candidates where ASR and raw OCR agree
  more strongly with each other than with canonical text.
content word can otherwise disappear inside a long high-scoring sentence.

## Acceptance

1. Run unit tests and `--preflight`.
2. Confirm the reported row count and missing-audio count.
3. Review low-scoring sentences while listening to their linked clips.
4. Verify proposed corrections against the PDF/raw OCR evidence when possible.
5. Apply corrections through a separate, validated data-repair change. Never
   bulk-replace canonical text directly from ASR output.
