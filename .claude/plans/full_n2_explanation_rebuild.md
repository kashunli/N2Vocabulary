# Plan: Re-explain All 1142 Unit Entries (N2)

## Scope

| Unit | Category | Entries | Index Range | Status |
|------|----------|---------|-------------|--------|
| 01 | 名詞 A | 100 | 1–100 | TODO |
| 02 | 動詞 A | 119 | 101–220 | TODO |
| 03 | 形容詞 A | 50 | 221–270 | DONE (new format) |
| 04 | 名詞 B | 190 | 271–460 | TODO |
| 05 | カタカナ A | 50 | 461–510 | TODO |
| 06 | 副詞A+接続詞 | 70 | 511–580 | TODO |
| 07 | 名詞 C | 86 | 581–666 | TODO |
| 08 | 動詞 B | 109 | 667–775 | TODO |
| 09 | カタカナ B | 50 | 776–825 | TODO |
| 10 | 形容詞 B | 50 | 826–875 | TODO |
| 11 | 名詞 D | 98 | 876–973 | TODO |
| 12 | 動詞 C | 100 | 974–1073 | TODO |
| 13 | 副詞B+連体詞 | 70 | 1074–1142+1 | TODO |

**Total TODO: 1092 entries across 12 units.**

## Execution Strategy

Process in **rounds of 5 units in parallel** (to stay under rate limits).
Each round launches 5 agents, each handling one full unit (~8-10 entries per sub-batch within the agent).

### Round 1: Units 1, 2, 5, 9, 10 (369 entries)
- Unit 1 (100 entries) → agent splits into ~12 sub-batches of 8-9
- Unit 2 (119 entries) → ~15 sub-batches
- Unit 5 (50 entries) → ~6 sub-batches
- Unit 9 (50 entries) → ~6 sub-batches
- Unit 10 (50 entries) → ~6 sub-batches

### Round 2: Units 6, 7, 13 (226 entries)
- Unit 6 (70 entries) → ~9 sub-batches
- Unit 7 (86 entries) → ~11 sub-batches
- Unit 13 (70 entries) → ~9 sub-batches

### Round 3: Units 4, 8, 11, 12 (497 entries)
- Unit 4 (190 entries) → ~24 sub-batches
- Unit 8 (109 entries) → ~14 sub-batches
- Unit 11 (98 entries) → ~12 sub-batches
- Unit 12 (100 entries) → ~13 sub-batches

## Per-Round Workflow

1. **Launch** 5 agents in parallel, each generating explanations for one unit's entries
2. **Collect** all agent outputs into `output/explanations_unitXX_all.json`
3. **Merge** via `python parse/scripts/merge_explanations.py output/explanations_unitXX_all.json`
4. **Verify** progress: `python parse/scripts/make_anki_listening.py` counts

## After All Rounds

1. `python parse/scripts/make_anki_listening.py`
2. `python parse/scripts/make_anki.py`
3. `python parse/scripts/make_html.py`

## Explanation Format (per entry)

```
**Natural English translation of the sentence.**

---

- **word（よみ）** — dictionary definition, part of speech. Usage note. [JLPT Nx]
- **grammar pattern** — function and nuance in this sentence. [JLPT Nx]
```

Key rules:
- Show kanji form for words commonly written in kana
- Verbs: 他動詞/自動詞 + counterpart
- JLPT level labels
- Literal meaning + semantic drift
- Flag adversative passives, wago/kango, Chinese false friends
- NO kanji breakdowns, NO chunk tables, NO summary
