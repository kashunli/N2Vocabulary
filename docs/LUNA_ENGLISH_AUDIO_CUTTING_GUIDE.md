# Luna Guide: Cutting English Word and Example-Sentence Audio

## Purpose

This guide adapts the workflow we used successfully for the N1 vocabulary
recordings to English-learning material with the same repeated structure:

```text
word -> pause -> example sentence -> longer pause -> next word -> ...
```

The central lesson is simple: **do not ask a speech model to invent all the
timestamps.** Use deterministic audio evidence to propose boundaries, use the
known lesson order and text to identify each item, and use Luna or ASR to
explain ambiguity and route uncertain cases to review.

For the N1 material, this approach produced 1,170 word clips and 1,170 sentence
clips from 93 vocabulary tracks. Every index was covered exactly once, all
2,340 files decoded, and the source-track hashes remained unchanged.

## The Most Important Mental Model

Cut the recording in two conceptual passes:

1. **Track -> learning-item pairs**: isolate each complete `word + sentence`
   item using the longer pauses between items.
2. **Pair -> word and sentence**: inside each item, use the first qualifying
   shorter pause as the word/sentence separator.

This is why the older workflow was called `cutTwice`. The two boundaries have
different meanings and should not be detected with one undifferentiated
"split on silence" rule.

Do not split on every pause. A speaker can pause naturally inside an example
sentence. In the N1 full-book scan, five sentences contained an additional
long pause. Treating all medium pauses as separators would have cut those
sentences in half. Our durable rule became:

> The first qualifying medium pause inside an item separates the headword from
> its example sentence. Later qualifying pauses remain part of the sentence
> and cause the item to be flagged for review.

## Authority and Evidence Hierarchy

When evidence conflicts, Luna should use this order:

1. **Immutable source audio** is the authority for what was actually spoken.
2. **Reviewed lesson manifest and item order** are the authority for which
   index is expected at each position.
3. **FFmpeg silence detection or equivalent signal analysis** is the default
   timing authority.
4. **Canonical word and example text** are identity evidence and define the
   expected output.
5. **ASR/Luna transcription** is supporting evidence, not permission to rewrite
   the lesson text or override a clear pause map.

Short isolated words are particularly easy for ASR to misrecognize. For N1,
sentence transcription and sequence position were much more reliable than
headword transcription. The same is likely in English for short words such as
`awe`, `owe`, `ate`, or `ought` and for homophones such as `their`/`there`.

## Responsibilities: Deterministic Code vs. Luna

Deterministic code should:

- discover source files and calculate SHA-256 fingerprints;
- read the canonical ordered item manifest;
- measure duration and run silence detection;
- propose item and word/sentence boundaries;
- cut files with FFmpeg;
- write manifests, progress records, and validation reports;
- enforce counts, index coverage, ordering, duration tolerances, and decoding;
- refuse to publish when a required invariant fails.

Luna should:

- compare candidate audio or ASR text with the expected word and sentence;
- use sequence context when a short word transcript is weak;
- classify ambiguous cases and explain the evidence;
- recommend a boundary from supplied candidate silences or waveform evidence;
- flag sentence-internal pauses, clipped phonemes, unexpected speech, or
  item-count disagreements;
- produce structured review decisions, never silent guesses.

Luna should **not**:

- overwrite, normalize, or rename source recordings;
- derive final cuts from prose alone when audio evidence is available;
- assume every silence is a semantic boundary;
- shift all later indices to hide one count mismatch;
- change canonical text merely because ASR produced different words;
- mark an item accepted when the expected count or order does not reconcile;
- replace an existing reviewed clip without an explicit versioned decision.

## Required Inputs

Before processing, build a human-readable manifest containing at least:

```json
{
  "lesson_id": "unit-03-track-02",
  "source_audio": "audio/unit-03-track-02.mp3",
  "source_sha256": "...",
  "language": "en",
  "items": [
    {
      "index": 41,
      "word": "meticulous",
      "sentence": "She kept meticulous records of every expense."
    }
  ]
}
```

Useful optional fields include the expected accent, speaker, phonemic form,
source page, lesson/unit number, and known spoken variants. Keep those fields
as evidence; do not let optional metadata silently replace the index, word, or
sentence contract.

If the exact track-to-index mapping is not known, do a no-write inventory and
pair-count scan first. Do not start bulk cutting while the address map is still
an inference.

## Phase 1: Preserve and Inventory the Sources

1. Treat source audio as immutable.
2. Record path, byte size, duration, codec, sample rate, channels, and SHA-256.
3. Separate introductions, instructions, jingles, and vocabulary tracks.
4. Record the expected number and index range of learning items for each track.
5. Keep raw inputs, work evidence, review clips, accepted clips, and caches in
   different directories.

A useful layout is:

```text
audio/                         immutable source tracks
work/audio-scan/               silence scans and candidate manifests
work/audio-review/             temporary listenable review clips
cache/asr/                     reproducible but disposable ASR results
clips/accepted/words/          accepted word clips
clips/accepted/sentences/      accepted sentence clips
reports/                       validation and review reports
```

Recalculate source hashes during final validation. This catches accidental
source replacement even when filenames have not changed.

## Phase 2: Calibrate on a Representative Pilot

Start with one complete track, not the whole course. Choose a track containing
short and long words, plosives or fricatives at clip edges, and at least one
sentence with a natural internal pause if possible.

Run silence detection at a relatively permissive floor so that one scan yields
many candidate intervals. Then evaluate a small bounded grid for:

- noise floor;
- minimum silence duration;
- item-gap threshold;
- word/sentence-gap threshold;
- leading and trailing safety edges.

The N1 recording used these **source-specific** values successfully:

| Parameter | N1 value | Meaning |
| --- | ---: | --- |
| Silence noise floor | `-38 dB` | Audio below this level was a silence candidate |
| Minimum detected silence | `0.12 s` | Preserve short candidate intervals for later classification |
| Between-item gap search | `1.25-1.55 s` | Candidate thresholds for separating complete pairs |
| Word/sentence gap search | `0.85-1.05 s` | Candidate thresholds inside a pair |
| Leading safety edge | `0.10 s` | Silence retained before detected speech |
| Trailing safety edge | up to `0.20 s` | Silence retained after detected speech |

These values are a starting hypothesis, **not English defaults**. English may
need different values because final plosives, aspiration, /s/ and /f/, weak
forms, and breath noise can extend beyond an energy-based speech boundary.
Calibrate from the actual narrator and recording chain.

The pilot is accepted only after:

- detected pair count equals the known item count;
- indices are ordered and contiguous for the track;
- every pair has a usable word/sentence separator;
- candidate clips decode;
- the first, middle, and last items sound complete;
- difficult final consonants and sentence endings are not clipped;
- ASR or Luna evidence broadly agrees with expected sequence and sentence text.

## Phase 3: Detect Complete Learning Items

Given silence intervals `(start, end)`, select internal intervals whose duration
meets the calibrated item-gap threshold. Use the midpoint of each selected
pause as the boundary between adjacent items. Ignore leading and trailing CD
silence as padding; they are not empty vocabulary items.

Conceptually:

```python
item_pauses = [
    pause for pause in silences
    if pause.duration >= item_gap
    and not pause.touches_track_edge
]
item_edges = [0.0] + [pause.midpoint for pause in item_pauses] + [track_duration]
items = adjacent_ranges(item_edges)
```

Do not select a threshold merely because it makes one track look plausible.
Evaluate the whole course in no-write mode and reconcile:

- per-track expected counts;
- total canonical item count;
- contiguous index ranges;
- independent page/lesson anchors, when available.

In the N1 experience, the dry run found exactly 1,170 pairs across 93 vocabulary
tracks. Raw OCR supplied 62 independent track-start observations: 58 agreed
directly, while four differed by one item. Targeted transcription of the first
pair resolved those four without shifting the rest of the book.

If a track count disagrees, stop and inspect that track. Possible causes include
an introduction, trailing CD silence, an unusually long sentence pause, a
missing recording, duplicated audio, or the wrong expected manifest. Never
repair a local mismatch by silently renumbering every later item.

## Phase 4: Split Each Item into Word and Sentence

Within an item range, collect pauses that meet the calibrated word/sentence-gap
threshold. Use the **first** qualifying pause:

```python
separators = qualifying_pauses_inside(item)
if not separators:
    flag("missing_word_sentence_separator")
else:
    split_pause = separators[0]
    word = speech_before(split_pause)
    sentence = speech_after(split_pause, through_item_end=True)
    if len(separators) > 1:
        flag("possible_sentence_internal_pause")
```

The sentence must continue through later pauses until the item boundary. Luna
may use the expected sentence, transcription, and waveform to decide whether a
later pause is grammatical phrasing or an actual recording anomaly, but it
must expose that judgment in the review record.

### Edge padding

Hard cuts exactly at estimated speech edges sound unnatural and can remove
meaningful phonemes. The N1 policy that survived listening review was:

- retain `0.10 s` before detected speech;
- retain up to `0.20 s` after detected speech;
- when the following silence is shorter than the trailing allowance, use half
  of that silence so adjacent clips do not overlap or consume each other.

For English, pay particular attention to:

- final /t/, /d/, /k/, /p/, and their releases;
- trailing /s/, /z/, /f/, /v/, and /th/ energy;
- aspirated initial consonants;
- sentence-final consonants before a breath;
- reduced or linked speech at the beginning of the example sentence.

Prefer a little clean silence to a clipped phoneme. Do not allow padding to
cross into neighboring speech.

## Phase 5: Ask Luna for Structured Review

Give Luna constrained evidence rather than an open-ended "cut this audio"
instruction. A useful request packet is:

```json
{
  "task": "review_vocabulary_pair_boundary",
  "lesson_id": "unit-03-track-02",
  "index": 41,
  "expected_word": "meticulous",
  "expected_sentence": "She kept meticulous records of every expense.",
  "item_range_seconds": [84.120, 91.840],
  "candidate_silences": [
    {"start": 85.010, "end": 85.940, "duration": 0.930},
    {"start": 88.200, "end": 88.690, "duration": 0.490}
  ],
  "candidate_transcript": "meticulous she kept meticulous records of every expense",
  "proposed_word_range": [84.120, 85.210],
  "proposed_sentence_range": [85.840, 91.840]
}
```

Require a machine-checkable response:

```json
{
  "decision": "accept",
  "word_range": [84.120, 85.210],
  "sentence_range": [85.840, 91.840],
  "confidence": "high",
  "flags": ["sentence_internal_pause_preserved"],
  "evidence": {
    "sequence_match": true,
    "word_identity_match": true,
    "sentence_identity_match": true,
    "word_end_complete": true,
    "sentence_end_complete": true
  },
  "note": "The first pause separates the isolated word from the sentence; the later pause is inside the sentence."
}
```

Allowed decisions should be a small enum such as:

- `accept`
- `adjust_boundary`
- `needs_human_review`
- `wrong_expected_item`
- `source_audio_problem`

Validate Luna's JSON schema before using it. A high confidence label never
overrides failed deterministic invariants.

## Phase 6: Review the Smallest Risky Set

Do not manually review thousands of ordinary items when structural checks can
reduce the problem. Export focused review clips for:

- first and last item of every track;
- any item with zero or multiple candidate separators;
- any track whose count disagrees with the manifest;
- low word/sentence transcript similarity;
- unusually short word clips or unusually long sentence clips;
- edge padding that nearly touches neighboring speech;
- unexpected narrator text, instructions, music, or noise;
- random samples across speakers, units, and duration buckets.

For the N1 run, the full scan reduced the special listening gate to five
sentence-internal-pause items. Only after the user accepted those samples did
the full-book exporter run.

## Phase 7: Export Resumably

Bulk export should be restartable and idempotent:

1. Read only an accepted track/index manifest.
2. Reproduce the accepted silence parameters for each track.
3. Refuse to continue if the detected pair count has changed.
4. For each output, record source, index, kind, start, end, requested duration,
   actual duration, and status in an append-only progress ledger.
5. If a target already exists, verify its duration and manifest identity. Skip
   only when it agrees; otherwise stop instead of overwriting it silently.
6. Write a versioned manifest after all clips are present.

Prefer stable index-based filenames:

```text
words/Word0041_meticulous.mp3
sentences/Sentence0041.mp3
```

The manifest—not filename parsing—should remain the authoritative mapping.
Including the word in a filename helps humans, but word spelling changes must
not change the item identity.

## Phase 8: Final Validation Before Publication

Acceptance should fail unless all of these are true:

- source hashes equal the inventory hashes;
- every expected source track is represented exactly once;
- every expected index has exactly one word clip and one sentence clip;
- no unknown indices or extra MP3s exist;
- index coverage is complete and contiguous where the course contract requires it;
- word comes before sentence and ranges are ordered and non-overlapping;
- every output decodes with FFmpeg;
- actual duration agrees with requested duration within a declared tolerance;
- the manifest file set exactly equals the filesystem file set;
- all required human/Luna review flags have an accepted decision;
- a listening sample confirms starts, endings, and semantic identity.

The N1 validator used a `0.03 s` maximum duration-difference gate and achieved
an observed maximum difference of `0.001 s`. Choose and record an explicit
tolerance suitable for the English encoder and container rather than relying
on visual inspection.

Do not point a learner-facing service at work or review directories. Publish
only the accepted manifest and its exact file set, then smoke-test real media
URLs through the same API/player path learners use.

## Failure Policy

| Failure | Required behavior |
| --- | --- |
| Pair count differs from expected count | Stop that track; inspect thresholds, source type, and manifest |
| No word/sentence pause exists | Keep the item intact and request manual/model boundary review |
| Multiple medium pauses exist | Use the first provisionally, retain later pauses in sentence, flag review |
| Short word ASR is wrong | Use sequence and sentence evidence; do not rewrite canonical word |
| Sentence ASR differs slightly | Treat as evidence; inspect audio before changing text or timing |
| Existing output has wrong duration | Stop; never silently accept or overwrite |
| Source hash changed | Invalidate the run and re-inventory the source |
| Introduction/music detected | Classify separately; do not consume a vocabulary index |
| Luna returns invalid JSON or unsupported claims | Reject the response and preserve the review item |
| Human judgment remains uncertain | Keep `needs_human_review`; do not publish as accepted |

## Compact Operating Prompt for Luna

The following can be placed in Luna's task instructions:

```text
You are reviewing proposed cuts for ordered English vocabulary recordings.
Each normal item contains an isolated headword followed by one example sentence.

Use the immutable audio and supplied candidate silence intervals as timing
evidence. Use the reviewed item index/order and canonical text as identity
evidence. ASR is supporting evidence only and may be wrong, especially for
short isolated words and homophones.

The long pause separates adjacent learning items. Inside an item, the first
qualifying medium pause separates the word from its example sentence. Preserve
later pauses inside the sentence unless clear audio evidence proves that they
start another item.

Never renumber later items to hide a mismatch. Never rewrite canonical text
from ASR alone. Never claim acceptance if counts, ordering, decoding, or source
fingerprints fail. Return only the required JSON schema. When evidence is not
enough, return needs_human_review and explain the exact ambiguity.

Check especially that English initial and final consonants are not clipped.
Prefer small clean-silence padding, but never include neighboring speech.
```

## What a Self-Taught Backend Programmer Can Learn Here

This workflow is a useful example of production data engineering, not just
audio editing:

- **Separate authority from evidence.** Signal processing, canonical content,
  ASR, and model judgment have different reliability and roles.
- **Turn assumptions into invariants.** Counts, ordering, hashes, duration, and
  exact file-set checks make corruption observable.
- **Design for replay and recovery.** Immutable inputs, manifests, append-only
  progress, and idempotent export make long jobs safe to resume.
- **Use staged confidence.** Pilot, dry run, focused review, bulk export, and
  final validation are distinct state transitions.
- **Keep the human review surface small.** Automation should identify the few
  ambiguous cases, not pretend ambiguity disappeared.
- **Treat AI output as untrusted structured input.** Constrain it with schemas,
  enums, deterministic validators, and explicit failure states.
- **Validate the consumer path.** Correct files on disk are not enough; the API
  and player must resolve the accepted clips learners actually hear.

The transferable engineering principle is: **make the model reason about
evidence, while code owns reproducibility and acceptance.**
