---
name: audio-clip-alignment
description: >
  Align a Japanese audio track to vocabulary entries using Whisper transcription,
  silence-bounded cutting, and LLM semantic matching. Replaces the old forward-search
  similarity algorithm. Use this skill whenever asked to fix misaligned clips, align
  new audio tracks, or redo clip cutting for the N2 vocabulary project.
---

# Audio Clip Alignment Skill

## When to Use

- Aligning new audio tracks that haven't been processed
- Fixing known misaligned clips from the old pipeline
- Re-cutting an entire unit with the new Whisper+LLM method

## Why This Works Better

The old pipeline used a forward-search algorithm matching Whisper transcripts to vocabulary entries via string similarity. It fails when:
1. Whisper misrecognizes words (大声→応勢) — similarity score drops
2. A single entry's sentence spans multiple Whisper segments — can't combine them
3. One misaligned entry cascades errors forward to all following entries

The new method:
1. **Whisper gives you all the raw material** — every word and sentence segment with timestamps
2. **ffmpeg silence detection gives you clean cut points** — boundaries fall in silence, never mid-word
3. **LLM does the matching** — handles ASR errors, combines multi-segment entries, and resolves ambiguities that string matching can't

No separate audit step is needed because the LLM matching is semantic, not lexical. If Whisper says `お父は気が短く` and the expected sentence starts with `弟は気が短く`, the LLM recognizes these as the same structure with a character error.

## Key Parameters

| Parameter | Value | Reason |
|-----------|-------|--------|
| Whisper model | `base` | Good accuracy/speed tradeoff for Japanese |
| `word_timestamps` | `True` | Provides finer segmentation for matching |
| Silence noise | `-32dB` | Lower catches more silence boundaries |
| Silence duration | `0.25s` | Critical for Japanese — 0.18s cuts mid-word on final consonants |
| ffmpeg codec | `libmp3lame -q:A 2` | Matches source MP3 quality |
| **Python version** | `python` (3.13) | **NOT `python3` (3.14)** — only 3.13 has `whisper` installed |

## Script Modes

| Mode | Flags | Behavior |
|------|-------|----------|
| Interactive | (no extra flags) | Runs Whisper → silence → prints prompt → waits for stdin JSON |
| Prompt only | `--prompt-only` | Runs Whisper → silence → prints prompt → exits |
| Non-interactive | `--llm-json <file>` | Runs Whisper → silence → reads mapping from file → cuts clips |
| Dry run | `--dry-run` | Runs full pipeline but doesn't cut audio files |

## Script

`parse/scripts/align_track_by_llm.py`

## Unit-Scale Workflow

For processing an entire unit (multiple tracks):

### Step A: Whisper ALL tracks first, then slide-match entries

**Do NOT estimate entry ranges from duration or segment counts.** Instead:

1. Run Whisper on every track in the unit
2. Collect all segment texts with their track name and timestamps
3. Slide-match each vocabulary entry against the full transcript — find which segment contains the word or sentence for each entry
4. This naturally discovers which entries belong to which track, including boundary drift

The matching logic:
- For each entry, search all Whisper segments for one whose text matches the entry's sentence/headword
- Use kana comparison (ignore kanji differences — Whisper often produces wrong kanji)
- The track that contains the match is the correct track for that entry

```python
import whisper
from pathlib import Path

def to_kana(text):
    """Strip everything except hiragana/katakana for fuzzy matching."""
    return ''.join(c for c in text if '\u3040' <= c <= '\u30ff')

# Whisper all tracks
tracks = sorted(Path("audio/UnitX .../").glob("*.mp3"))
all_segments = []
model = whisper.load_model('base')
for t in tracks:
    result = model.transcribe(str(t), language='ja', word_timestamps=True)
    for seg in result['segments']:
        all_segments.append({
            'track': t.name,
            'start': seg['start'],
            'end': seg['end'],
            'text': seg['text'],
            'kana': to_kana(seg['text']),
        })

# Match entries to segments via sliding window
for entry in unit_entries:
    entry_kana = to_kana(entry['sentence'])
    for seg in all_segments:
        if entry_kana in seg['kana'] or seg['kana'] in entry_kana:
            print(f"Entry {entry['index']} -> track {seg['track']}")
            break
```

This gives you the exact entry→track mapping. Then generate entries JSON files per track based on actual matches.

### Step B: Generate entry JSON files

Create `output/unitX_entries/entries_NN.json` for each track based on the Step A mapping:
```bash
python3 -c "
import json
from pathlib import Path
combined = json.load(open('output/vocabulary_combined.json'))
by_index = {entry['index']: entry for entry in combined}

# Use actual track-to-entry mapping from Step A
ranges = [
    ('audio/UnitX .../02 1-02.mp3', 1, 17),
    ('audio/UnitX .../03 1-03.mp3', 18, 39),
    # ... from Step A matching results
]
out_dir = Path('output/unitX_entries')
out_dir.mkdir(parents=True, exist_ok=True)

for track, s, e in ranges:
    entries = [{'index': idx, 'unit_number': X,
                'headword': by_index[idx].get('kanji', ''),
                'reading': by_index[idx].get('reading', ''),
                'sentence': by_index[idx].get('sentence_text', '')}
               for idx in range(s, e+1) if idx in by_index]
    num = Path(track).stem.split()[0]
    (out_dir / f'entries_{num}.json').write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')
"
```

### Step C: Per track — Whisper → LLM match → Cut

**1. Get the Whisper prompt:**
```bash
python parse/scripts/align_track_by_llm.py \
    --track "audio/UnitX .../02 1-02.mp3" \
    --entries-json "output/unitX_entries/entries_02.json" \
    --unit X --prompt-only
```

**2. Review Whisper output and create mapping JSON** in `output/unitX_mappings/mapping_NN.json`.

The mapping format:
```json
[
  {
    "index": 1,
    "word": {"start": 0.00, "end": 1.28},
    "sentence": {"start": 2.00, "end": 5.50}
  }
]
```

**Two scenarios — pick the right source of truth for cut times:**

The script's `snap_to_silence()` has a **narrow ±0.15s tolerance** — it nudges a time onto a nearby silence edge, it does not search. Which source you feed into the mapping depends on whether Whisper gave you usable edges:

### Scenario A — Whisper returned separate segments for word and sentence

This is the normal case. Whisper's segment boundaries fall within ~0.1–0.2s of the real silence edges. Use Whisper segment `[start, end]` times directly in the mapping; `snap_to_silence()` will pull them onto the nearest silence edge within its tolerance window.

### Scenario B — Whisper merged word + sentence into one segment

Whisper sometimes returns a single segment covering both the headword and its example sentence (e.g. `[77.92, 85.88] はりきる。入社第一日目、娘は…`). In that case:

- **Whisper offers no split point between word and sentence.** Its outer edges (77.92, 85.88) are the outer edges of the whole merged unit — they are not candidates for the internal word↔sentence split.
- **Do not invent a midpoint** (e.g. "split at ~79s"). An invented time has no relationship to actual silence; `snap_to_silence` will fail to find a silence edge within its ±0.15s window and fall back to raw timing, producing a cut that lands inside speech or inside a silence gap.
- **Read the ffmpeg silence table instead.** The prompt's `## Silence boundaries` section lists every `silence_start` / `silence_end` on the track. Find the silence edges *inside* the merged Whisper segment and use those as the cut points directly.

**How to label the speech regions inside a merged segment:**

Between the Whisper segment's outer edges, there will be one or more speech regions separated by silence gaps. Label them by position + duration:
- A short leading speech region (~0.4–1.2s) followed by silence is the **word** (headword spoken alone).
- The longer region(s) after that, possibly split by mid-sentence pauses, are the **sentence**.

If the merged segment has enough silence structure to be ambiguous (e.g. three similar-duration regions, or a very short first region that might be a false start), **cut each candidate region into a temporary clip and re-transcribe it** with Whisper on the isolated clip — the LLM can then identify which clip contains the headword reading vs. which contains the full example sentence. This works because Whisper transcribes short clips more reliably than the merged segment it originally produced.

Worked example (entry 113 on `08 1-08.mp3`):
- Whisper: `[77.92, 85.88] はりきる。入社第一日目、娘は張り切って出勤した。` (merged)
- ffmpeg silence edges inside that range:
  `silence_end 79.850 → silence_start 80.457` (speech region, ~0.6s)
  `silence_end 81.276 → silence_start 82.958` (speech region, ~1.7s)
  `silence_end 83.568 → silence_start 85.927` (speech region, ~2.4s)
- Correct mapping: `word {79.850, 80.457}`, `sentence {81.276, 85.927}` — sentence spans two speech regions joined across a mid-sentence pause.

### Other patterns

| Pattern | What to do |
|---------|-----------|
| **Multi-segment sentence** (Whisper split sentence at a pause) | Use `silence_end` before first segment to `silence_start` after last segment |
| **ASR errors** | Note them in the `note` field. Match by context and sentence structure, not exact text |

**3. Cut clips (non-interactive):**
```bash
python parse/scripts/align_track_by_llm.py \
    --track "audio/UnitX .../02 1-02.mp3" \
    --entries-json "output/unitX_entries/entries_02.json" \
    --unit X \
    --output "output/review_unitX_track_02.json" \
    --llm-json "output/unitX_mappings/mapping_02.json"
```

### Step D: Merge all track results

```bash
python3 -c "
import json, glob
all_records = []
for f in sorted(glob.glob('output/review_unitX_track_*.json')):
    records = json.load(open(f, encoding='utf-8'))
    all_records.extend(records)
    print(f'{f}: {len(records)} records')
json.dump(all_records, open('output/review_unitX_all.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print(f'Total: {len(all_records)} records')

# Check for duplicates
indices = [r['index'] for r in all_records]
dups = [i for i in set(indices) if indices.count(i) > 1]
print(f'Duplicates: {dups if dups else \"none\"}')
"

python parse/scripts/merge_assigned_clips.py output/review_unitX_all.json
```

### Step E: Regenerate outputs

```bash
python parse/scripts/make_html.py
python parse/scripts/make_anki.py
python parse/scripts/make_anki_listening.py
copy output\N2Words.apkg D:\n2Prepare\ankiCardsToBuilt\
copy output\N2Words_listening.apkg D:\n2Prepare\ankiCardsToBuilt\
```

## Common ASR Error Patterns

These are the misrecognitions Whisper makes on this audio:

| Expected | Whisper says | Notes |
|----------|-------------|-------|
| 大声 (おおごえ) | 応勢 / 応援 | |
| 弟 (おとうと) | お父 / 音音 | |
| 犯人 (はんにん) | 判人 | |
| 刑事 (けいじ) | 経時 | |
| 駐車 (ちゅうしゃ) | 中車 | Unit 1 |
| 違反 (いはん) | 遺判 | Unit 1 |
| 謙遜 (けんそん) | 検損 | Unit 1 |
| 徒歩 (とほ) | 東方 | Unit 1 |
| 斜め (ななめ) | 7目 | Unit 1 |
| 費用 (ひよう) | 日曜 | Unit 1 |
| 定価 (ていか) | 低下 | Unit 1 |
| 社長 (しゃちょう) | ニューシャ | |
| 死 (し) | しよ | |
| 景気 (けいき) | ケーキ | |
| 強引な (ごういんな) | ゴインナ / ゴインニ | Unit 3 |
| 険しい (けわしい) | ケワシー | Unit 3 |
| 騒々しい (そうぞうしい) | 想像し | Unit 3 |
| 慌ただしい (あわただしい) | あわただし | Unit 3 |
| 憎らしい (にくらしい) | ニクラシー | Unit 3 |
| 憎い (にくい) | ニクイ | Unit 3 |
| 強気な (つよきな) | 強きな | Unit 3 |
| 頑固な (がんこな) | ガンコナ | Unit 3 |
| 過剰な (かじょうな) | 家常な | Unit 3 |
| 深刻な (しんこくな) | 新国な | Unit 3 |
| 安易な (あんいな) | 愛いな | Unit 3 |
| 気楽な (きらく) | きらく | Unit 3 |
| やむを得ない | 山を得ない | Unit 3 |

## Verified Results

### Unit 01 名詞A (entries 1-100)

| Metric | Value |
|--------|-------|
| Tracks processed | 6 content tracks (02-07) + 1 intro-only track (01, 9s, skipped) |
| Entries aligned | 100/100 |
| Word + sentence clips | 100 each (200 total) |
| Match method | `llm_whisper_silence` |
| Boundary adjustments | 3 entries drifted across tracks (17 on track 02 tail, 69 on track 05 tail, 87 on track 06 tail) |
| Missing files | 0 |
| Duplicate indices | 0 |

**Key findings:**
- Track 01 (9s) contained only the title/intro — no vocabulary entries.
- Entry 17 (才能) was on track 02's tail, not track 03. Initial duration-based estimate was wrong — Whisper content should always be used for boundary discovery.
- Used Whisper segment timestamps directly in mapping JSON when Whisper returned separate segments for word and sentence (Scenario A). For merged segments (Scenario B), silence edges from ffmpeg must be used as the internal cut points — `snap_to_silence()` only nudges within ±0.15s, it does not bridge multi-second gaps.

### Unit 02 動詞A (entries 101-220)

| Metric | Value |
|--------|-------|
| Tracks processed | 9 (08-16) |
| Entries aligned | 119/120 (entry 171 missing from DB) |
| Word + sentence clips | 119 each |
| Match method | `llm_whisper_silence` |
| ASR error notes | 84/119 |
| Missing files | 0 |
| Duplicate indices | 0 |

### Unit 03 形容詞A (entries 221-270)

| Metric | Value |
|--------|-------|
| Tracks processed | 5 (17-21) |
| Entries aligned | 50/50 |
| Word + sentence clips | 50 each |
| Match method | `llm_whisper_silence` |
| Boundary adjustments needed | 4/5 tracks had entry drift |
| Missing files | 0 |
| Duplicate indices | 0 |

## No Separate Audit Needed

The old pipeline required `audit_review_candidates.py` as a second pass because the forward-search similarity scores were unreliable. With LLM semantic matching:
- Whisper misrecognitions are handled by the LLM's contextual understanding
- Multi-segment combining is explicit in the matching step
- Silence-bounded cuts eliminate mid-word clipping

## Optional verification via `--rescore`

After cutting, re-run each clip through Whisper and score it against the expected reading/sentence using kana-only `difflib.SequenceMatcher` similarity:

```bash
python parse/scripts/align_track_by_llm.py \
    --track "audio/UnitX .../02 1-02.mp3" \
    --entries-json "output/unitX_entries/entries_02.json" \
    --unit X \
    --output "output/review_unitX_track_02.json" \
    --llm-json "output/unitX_mappings/mapping_02.json" \
    --rescore
```

When `--rescore` is set, the review JSON's `word_score` / `sentence_score` fields are populated. Rough quality bands observed in practice:

| Score | Interpretation |
|-------|----------------|
| ≥ 0.90 (word) / ≥ 0.80 (sentence) | Clean match — no review needed |
| 0.50–0.80 | ASR error in either the clip or the expected text — usually still correct, but worth spot-checking |
| < 0.50 | Likely misaligned or bad cut — manual review recommended |

Without `--rescore`, these fields stay `null` — the output then reflects only "did we produce a file," not objective alignment quality.

## Snap-to-silence tolerance

`snap_to_silence()` looks for a silence edge within `SNAP_TOLERANCE_SECONDS` (currently `0.15s`) on each side of the LLM-chosen time. When no silence edge is found in that window, the script falls back to `Whisper time ± 0.1s` and prints a `[WARN]` line to stderr. Watch for those warnings — they mean the "silence-bounded cut" guarantee did not apply for that boundary.
