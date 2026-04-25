# Vocabulary Audio Pipeline Notes

This document explains how the combined vocabulary + audio clipping project was started, what decisions were made, what problems came up, and how the current implementation works.

The implementation lives in:

- [`../scripts/build_vocab_audio_dataset.py`](../scripts/build_vocab_audio_dataset.py)

The generated outputs live in:

- [`output/vocabulary_combined.json`](/mnt/d/n2Prepare/materialToLearn/N2Vocabulary/output/vocabulary_combined.json)
- [`output/audio_alignment_manifest.json`](/mnt/d/n2Prepare/materialToLearn/N2Vocabulary/output/audio_alignment_manifest.json)
- [`output/review_still_needs_human.json`](/mnt/d/n2Prepare/materialToLearn/N2Vocabulary/output/review_still_needs_human.json)
- [`output/clips`](/mnt/d/n2Prepare/materialToLearn/N2Vocabulary/output/clips)

## Project Goal

The goal was to convert page-level OCR JSON into one book-level vocabulary dataset and then find, for each word entry:

1. the spoken headword in the audio
2. the spoken first example sentence in the audio
3. silence-bounded clip ranges for both

The clips are written as:

- `word{index}.mp3`
- `sentence{index}.mp3`

where `index` is the global book entry number.

## Initial Exploration

The project started with a structure and data survey:

1. Confirm the folder layout under [`json`](/mnt/d/n2Prepare/materialToLearn/N2Vocabulary/json), [`audio`](/mnt/d/n2Prepare/materialToLearn/N2Vocabulary/audio), and [`parse/structured`](/mnt/d/n2Prepare/materialToLearn/N2Vocabulary/parse/structured).
2. Inspect `page_009.json` because that is where the first vocabulary entry begins.
3. Check whether the existing structured parser already preserved useful metadata like unit boundaries.
4. Check the audio folder naming and track numbering patterns.

Two important findings came out of that survey:

- The root [`json`](/mnt/d/n2Prepare/materialToLearn/N2Vocabulary/json) files were cleaner than `parse/structured` for entry content, especially on later pages.
- The structured output under [`parse/structured`](/mnt/d/n2Prepare/materialToLearn/N2Vocabulary/parse/structured) was still valuable because it preserved unit boundaries more consistently.

That led to the first architecture decision:

- Use `json/` for entry content.
- Use `parse/structured/` only to infer where units begin.

## Important Product Assumption

The project needed one critical assumption before audio matching could be designed:

- each CD/audio item contains the headword and the first example sentence

This assumption came from the study-guide page summary in:

- [`parse/proofRead/parseByGemini/output/markdown/page_003.md`](/mnt/d/n2Prepare/materialToLearn/N2Vocabulary/parse/proofRead/parseByGemini/output/markdown/page_003.md)

That note says the CD contains the headword and the first example sentence for each entry.

This assumption drove the rest of the pipeline:

- `sentence_text` is always the first example sentence
- audio matching looks for `word + first sentence`

## Major Design Decisions

### 1. Keep OCR source content mostly untouched

The implementation does not rewrite source pages. It performs only light normalization while extracting entries:

- strip leading bullets from examples
- normalize HTML entities
- derive a spoken headword when an entry only has a reading plus `スル`

Reason:

- aggressive cleanup risks silently changing the learning content
- preserving the original text makes review easier

### 2. Use silence boundaries, not ASR timestamps, for clip cutting

This was the most important technical decision in the project.

At first, Whisper seemed useful for both text and timestamps. But that would have made the clip boundaries dependent on ASR timing quality, which is not reliable enough for this material.

The final rule became:

- Whisper is used only for text identity and rough segment grouping.
- `ffmpeg` silence detection is the source of truth for clip start and stop times.

Why this is better:

- the recordings have clear pauses between many items
- silence boundaries are stable even when the transcript is imperfect
- this matches the requirement that word and sentence boundaries should fall within silence ranges

### 3. Match unit-by-unit, not across the whole book at once

The audio is organized by unit, so matching the whole book against the whole audio library would create unnecessary ambiguity.

The pipeline groups entries by unit first, then aligns only within that unit’s track set.

Benefits:

- smaller search space
- fewer false matches
- easier debugging

### 4. Allow review candidates instead of forcing certainty

The system explicitly keeps uncertain matches in the output instead of pretending everything is correct.

This is why the manifest includes:

- `confidence`
- `word_confidence`
- `sentence_confidence`
- `needs_review`
- `review_reasons`

That decision was important because OCR and ASR are both noisy in this project.

## Problems Encountered and Fixes

### Problem 1: Some source rows had missing entry numbers

While running the first extractor pass, the script failed because some rows had no numeric `number`.

Fix:

- sort malformed rows to the end
- skip rows without a valid integer `number`

Reasoning:

- a missing global index is too important to guess
- skipping is safer than inventing a fake index

### Problem 2: The source JSON had duplicate global indices

The root JSON files contain a small number of duplicated entry numbers caused by OCR/parser issues.

Examples discovered during implementation:

- duplicated indices around 584, 589, 891, 892, 893, 894, 966, 975

Fix:

- deduplicate by index
- keep the “better” entry using a simple quality heuristic

The heuristic prefers:

1. entry with kanji/headword
2. entry with a first example sentence
3. entry with more examples
4. entry with more populated translations
5. earlier page when tied

Reasoning:

- the combined dataset needs a unique global key
- preserving the more complete record is better than crashing the pipeline

### Problem 3: Audio folder parsing initially missed `Unit1`

The first version expected folder names like `Unit 1 ...`, but the actual folders are named like `Unit1 ...`.

Fix:

- change the unit regex from requiring a space to allowing optional space

Reasoning:

- normalize input shape early so the rest of the pipeline can assume a simple integer unit key

### Problem 4: One-track-to-one-contiguous-entry-slice was too brittle

An early version assumed each track continued neatly from where the previous track ended in the entry list.

This failed in practice because:

- track boundaries do not always align cleanly with entry boundaries
- short words can accidentally resemble other entries

Fix:

- each track now searches forward through the unit’s remaining entries
- later stronger matches can replace weaker earlier ones

Reasoning:

- this preserves the in-order property while avoiding hard assumptions about exact track breaks

### Problem 5: Short headwords were often transcribed badly

Whisper frequently mishears very short headwords even when the sentence is correct.

Examples:

- one- or two-mora words
- words with homophones
- OCR-damaged headwords

Fix:

- lower the importance of headword transcription when the sentence match is very strong
- keep review flags for weak sentence matches

Reasoning:

- the sentence carries more distinguishing information than the isolated headword
- but strong sentence match should not hide truly weak sentence evidence

## Current Matching Strategy

The current alignment logic uses two candidate shapes:

### Same-segment candidate

Used when Whisper hears the headword and sentence inside one coarse segment.

Example shape:

- `人生 幸せな人生を送る`

How it is cut:

- first silence chunk in the segment -> `word`
- remaining silence chunks -> `sentence`

### Split-segment candidate

Used when Whisper hears the headword and sentence as adjacent segments.

Example shape:

- segment A: `個性`
- segment B: `子どもたちの個性を伸ばすような教育がしたい`

How it is cut:

- silence chunks belonging to segment A -> `word`
- silence chunks belonging to segment B -> `sentence`

The matcher chooses the better of these two candidate shapes.

## Why `faster_whisper` Was Kept

There was a question during implementation about whether `openai-whisper` would be better.

Decision:

- keep `faster_whisper` for now

Reason:

- the project does not rely on Whisper timestamps anymore
- it only needs reasonably fast local transcription for text matching
- `faster_whisper` already worked in the environment and kept full runs practical

If you want to experiment later, the recognizer can be swapped more easily now because the clip timing does not depend on the ASR engine.

## Windows Vulkan Transcription Backend

Later in the project, the bottleneck shifted from alignment logic to repeated
transcription of many small audio windows during review rescue. That led to a
new design goal:

- keep the Python matching logic in WSL
- keep `ffmpeg` for silence boundaries
- move heavy transcription work onto the Windows AMD GPU

The chosen backend was `whisper.cpp` with Vulkan.

Reasons:

- the machine has an AMD GPU, so CUDA-centric options were a poor fit
- `whisper.cpp` has first-class Vulkan support
- it can be called as a CLI from Python, which made it easy to slot into the
  existing audit pipeline without rewriting the matcher

### What was built

A Windows helper lives under:

- [`tools/whispercpp-windows/setup_whispercpp_vulkan.bat`](/mnt/d/n2Prepare/materialToLearn/N2Vocabulary/tools/whispercpp-windows/setup_whispercpp_vulkan.bat)
- [`tools/whispercpp-windows/README.md`](/mnt/d/n2Prepare/materialToLearn/N2Vocabulary/tools/whispercpp-windows/README.md)

That helper:

1. finds the installed Vulkan SDK, even if `VULKAN_SDK` is not exported
2. clones `whisper.cpp`
3. builds `whisper-cli` with `GGML_VULKAN=ON`
4. copies the CLI and required DLLs into the project-local helper folder

The audit script was extended so transcription is now pluggable:

- `openai_whisper`
- `whisper_cpp`

The Python side still treats ASR as text evidence only. The silence-bounded
`ffmpeg` chunking remains the final source of truth for timing.

### A subtle parsing problem and how it was fixed

The first `whisper.cpp` Windows JSON integration failed, but not because the
model output was unusable. The real issue was encoding behavior:

- the JSON file was mostly UTF-8
- some token-level entries contained malformed bytes
- strict UTF-8 decoding failed
- a naive UTF-16 fallback turned valid JSON into gibberish

The fix was:

- detect UTF-16 only when BOM or heavy NUL-byte evidence exists
- otherwise decode as UTF-8 with replacement as a last-resort recovery path

That preserved the top-level JSON structure and the segment text we actually
needed, while ignoring corruption in the detailed token list.

### Validation

The Windows Vulkan binary was validated from WSL:

- it reports the AMD Vulkan device successfully
- it transcribes review clips through the Python audit backend

One sample result:

- expected: `出世もしたいが、仕事ばかりの人生も嫌だ。`
- Windows Vulkan `whisper.cpp`: `出世もしたいが 仕事ばかりの人生も嫌だ`

That was a good sign that the Windows GPU path was not only built, but actually
useful for the review workload.

## Output Interpretation

### `vocabulary_combined.json`

This is the main flattened vocabulary dataset.

Each entry includes:

- original book identity
- unit and page location
- normalized headword fields
- first example sentence
- audio alignment fields

### `audio_alignment_manifest.json`

This is the operational alignment table.

Use it for:

- auditing matches
- checking confidence
- tracing clips back to the source track

### `review_still_needs_human.json`

This is the current queue to inspect manually after the audit pass removes easier false positives.

Common reasons:

- `no_matching_track_content`
- `weak_sentence_match`
- `weak_word_match`

### `output/clips`

Contains the actual extracted audio files for matched entries.

## Current Results

At the time of writing, the full run produced:

- 1098 combined entries
- 737 matched entries with clips
- 361 unmatched entries
- 699 entries flagged for review

This means the pipeline is already useful, but it is still a best-effort automatic alignment system rather than a fully trusted gold-standard alignment.

## Second-Pass Audit Layer

After the first alignment pass, a second-pass audit script was added:

- [`../scripts/audit_review_candidates.py`](../scripts/audit_review_candidates.py)

Its purpose is to reduce false-positive review flags without pretending to solve the remaining hard cases.

### Why a second pass was needed

Some review items looked correct to a human even though the first pass still marked them for review.

Example pattern:

- the word is clearly the expected word or reading
- the sentence is close but contains obvious ASR substitutions
- the item appears between the correct previous and next entries on the same track

This is exactly the kind of case where timeline position is more trustworthy than raw transcript wording.

### Main idea

The second-pass audit combines three evidence sources:

1. fuzzy similarity between the expected sentence and the transcript excerpt
2. exact or fuzzy presence of the expected word/reading in the transcript
3. monotonic neighbor support on the same track

Monotonic neighbor support means:

- previous item, current item, and next item are on the same track
- their timestamps are present
- the current item’s window falls cleanly between the previous and next windows

This turns the trusted index order into usable evidence.

### What it outputs

- [`output/review_audit_results.json`](/mnt/d/n2Prepare/materialToLearn/N2Vocabulary/output/review_audit_results.json)
- [`output/review_auto_approved.json`](/mnt/d/n2Prepare/materialToLearn/N2Vocabulary/output/review_auto_approved.json)
- [`output/review_still_needs_human.json`](/mnt/d/n2Prepare/materialToLearn/N2Vocabulary/output/review_still_needs_human.json)

### Current audit result

The second-pass audit auto-approved a subset of the original review items and left the rest for human review.

This means the workflow now has three layers:

1. initial alignment
2. conservative review flagging
3. conservative auto-clear of easy false positives

That layered approach is safer than trying to make the first pass overly aggressive.

## Audit Redesign Notes

After inspecting real review examples, the next design improvement became clear: the existing second-pass audit still relied too much on raw surface-text comparison.

Example:

- truth:
  - `reading = ふうふ`
  - `sentence_1 = 小林さん夫婦はいつも仲がいい。`
- transcript excerpt:
  - `ふふ / 小売さんふふはいつもなかがいい`

A human can see this is probably correct because:

- `ふうふ` and `ふふ` are phonetically very close
- `なかがいい` is clearly the reading of `仲がいい`
- the item sits in the correct position between neighboring entries on the same track

But a plain kanji/surface comparison undervalues this.

### Main insight

For this dataset, the most reliable signals are not all equally important.

The evidence should be ranked roughly like this:

1. silence-bounded timeline position within the track
2. sentence-level phonetic similarity
3. explicit hit on the expected word or reading
4. overall transcript shape and length
5. detailed middle-token accuracy

This means a transcript can still be good enough even when the middle contains obvious ASR substitutions, as long as:

- the beginning is right
- the ending is right
- the item is in the right place

### Planned kana-based comparison

The next stronger audit should convert both sides to kana or hiragana before comparison.

Expected side:

- `夫婦` -> `ふうふ`
- `小林さん夫婦はいつも仲がいい。` -> roughly `こばやしさんふうふはいつもなかがいい`

Transcript side:

- `ふふ / 小売さんふふはいつもなかがいい`

Comparing kana-to-kana is better than comparing:

- kanji sentence vs noisy transcript

because it reduces false penalties caused by:

- kanji vs kana mismatch
- ASR substituting near-homophones
- mixed writing systems

### Available tools in this environment

The environment already has:

- `fugashi`
- `unidic`
- `jaconv`

That makes the next implementation path straightforward:

1. tokenize the truth sentence with `fugashi`
2. extract readings from `unidic`
3. convert katakana readings to hiragana with `jaconv`
4. normalize the transcript into a hiragana-like comparison string

### Boundary-weighted matching

The analysis also showed that the beginning and ending of the sentence matter more than the middle.

Reason:

- the headword is spoken at the start
- the sentence ending often survives ASR better than the middle
- the middle is where content-word substitutions and OCR noise show up most

So the next scoring model should split the sentence into regions:

- `start_score`
- `end_score`
- `full_score`

Suggested weighting:

- `start_score`: 40%
- `end_score`: 40%
- `full_score`: 20%

This would promote examples like:

- `長男`
- `夫婦`

where the transcript is clearly anchored correctly even if some middle words are wrong.

### Length-aware auditing

Another useful signal is length consistency.

If the expected kana sentence and the transcript kana sentence differ too much in length, that often means:

- a chunk is missing
- two chunks were merged
- the wrong segment was matched

Suggested rule:

- no penalty when transcript length is within about `80%` to `125%` of expected
- soft penalty outside that range
- strong suspicion of missing content when below about `65%`

This is especially useful for catching partial transcripts that otherwise look close.

### Separate scoring for word and sentence clips

The word clip and sentence clip should not be judged with the same standard.

Word clip:

- compare mostly against the expected reading
- allow compressed long vowels and small mora loss
- examples:
  - `ふうふ` vs `ふふ`
  - `ひっしゃ` vs `ヒッシャ`

Sentence clip:

- compare the sentence in kana
- weight beginning and ending more heavily
- use length ratio
- use neighbor support

### Structural evidence from trusted order

The project already trusts the global vocabulary index.

That means if:

- item `N-1`, `N`, and `N+1` are on the same track
- their timestamps are monotonic
- `N` has a decent phonetic sentence match

then `N` deserves a stronger approval bias even if the middle text is noisy.

This is the core structural idea behind the redesign:

- book order is not just metadata
- book order is evidence

### Proposed next scoring model

The next audit version should compute:

- `word_reading_score`
- `sentence_kana_score`
- `sentence_start_score`
- `sentence_end_score`
- `length_score`
- `neighbor_score`

Then combine them, for example:

- `0.20 * word_reading_score`
- `0.20 * sentence_kana_score`
- `0.20 * sentence_start_score`
- `0.20 * sentence_end_score`
- `0.10 * length_score`
- `0.10 * neighbor_score`

Plus hard guards:

- if no track placement support and weak sentence ending, keep review
- if transcript is far too short, keep review
- if both sentence start and sentence end are weak, keep review

### Why this redesign matters

The current second-pass audit already improves the review queue, but the redesign would make it much more aligned with how a human actually judges these clips.

Humans do not require perfect literal transcript agreement.

They usually look for:

- right word or reading near the front
- right sentence shape
- right ending
- right place between neighboring items

The redesign simply turns that human reasoning into explicit machine rules.

## How to Run the Pipeline

Full run:

```bash
python3 parse/scripts/build_vocab_audio_dataset.py
```

Extraction only:

```bash
python3 parse/scripts/build_vocab_audio_dataset.py --skip-audio
```

Alignment without cutting clips:

```bash
python3 parse/scripts/build_vocab_audio_dataset.py --skip-clips
```

Single unit debugging:

```bash
python3 parse/scripts/build_vocab_audio_dataset.py --units 1 --skip-clips
```

## Recommended Next Improvements

If you continue this project, the highest-value next steps are:

1. Add a small manual review tool that plays the source track around the suggested timestamps.
2. Add a correction file so reviewed alignments can override automatic matches without changing source data.
3. Improve headword alias generation for OCR-damaged pages, especially later units.
4. Consider a better Japanese ASR model only for transcript quality, not timing.
5. Add per-unit summary stats to make debugging easier.

## Development Philosophy Used Here

The project was built with a few strong principles:

- do not modify source OCR pages
- separate extraction from alignment from clip cutting
- trust signal processing for boundaries more than ASR timestamps
- keep uncertain cases explicit
- prefer recoverable output over pipeline failure

That is the main shape of the current system.
