# OCR Text Parsing Guide

This guide describes the target structure expected from the parser implementation in [`../scripts/parse_book.py`](../scripts/parse_book.py).

This document explains how to parse OCR text from this book into structured data.

The goal is to convert noisy page-level OCR like:

```text
1 じんせい 人生 life／人生／인생
・幸せな人生を送る。 ・人生経験が豊富な人の話は面白い。
間 _を送る 会 _経験、_観 類 ―生、生涯
```

into stable JSON like:

```json
{
  "id": 1,
  "reading_kana": "じんせい",
  "kanji": "人生",
  "translations": {
    "en": "life",
    "zh": "人生"
  },
  "examples": [
    "幸せな人生を送る。",
    "人生経験が豊富な人の話は面白い。"
  ],
  "relation_blocks": [
    {
      "marker": "間",
      "label_jp": "連",
      "type": "collocation",
      "content": "_を送る",
      "items": ["_を送る"]
    },
    {
      "marker": "会",
      "label_jp": "合",
      "type": "compound",
      "content": "_経験、_観",
      "items": ["_経験", "_観"]
    },
    {
      "marker": "類",
      "label_jp": "類",
      "type": "synonym",
      "content": "―生、生涯",
      "items": ["―生", "生涯"]
    }
  ]
}
```

## 1. Core Idea

OCR parsing should be layout-aware, not text-only.

For these vocabulary pages, the parser should assume this recurring entry pattern:

1. Entry header line
2. One or more example lines
3. One or more relation lines

That is the basic grammar of the page.

## 2. Page Types

Before parsing individual lines, classify the page.

Common page types in this project:

- `title_page`
- `study_guide`
- `table_of_contents`
- `vocabulary`
- `exercise`
- `column`
- `summary`
- `index`

For OCR parsing, `vocabulary` and `exercise` are the most important.

## 3. Vocabulary Entry Format

Canonical shape:

```text
<id> <reading> <headword> <translations>
<example lines>
<relation lines>
```

OCR sometimes splits the header across two lines, especially in verb sections:

```text
# 133 ひっぱる
## 9引っ張る
pull; persuade (a person) to join ~ / 払, 拽; 拉拽 / 習다, 당기다, 끌어들이다
```

In that layout:

- the first line still provides `id` and `reading_kana`
- the second line provides the surface form and grammatical marker
- OCR variants such as leading `9` or `ヨ` in that second line should be treated as a transitive-style `ヲ` marker

Example:

```text
1 じんせい 人生 life／人生／인생
・幸せな人生を送る。 ・人生経験が豊富な人の話は面白い。
間 _を送る 会 _経験、_観 類 ―生、生涯
```

### 3.1 Header Line

Header line fields:

- leading integer -> `id`
- first kana token -> `reading_kana`
- following Japanese surface form -> `kanji` or `headword`
- trailing multilingual gloss block -> `translations`

Expected translation order:

- first = English
- second = Chinese
- third = Korean

Inline English glosses can include a leading parenthetical qualifier and should stay intact as one English translation.

Example:

```text
6 ふうふ 夫婦 (married) couple／夫妇，夫妻／부부
```

should parse with:

- `kanji = "夫婦"`
- `translations.en = "(married) couple"`
- `translations.zh = "夫妇，夫妻"`

Delimiter:

- usually `／`
- occasionally `/`
- when OCR mixes both, split at the earliest translation separator in the line

Example:

```text
100 かち 価値 value /价值／外国
```

should parse with:

- `kanji = "価値"`
- `translations.en = "value"`
- `translations.zh = "价值"`

### 3.2 Example Lines

Example lines usually:

- start with `・`
- or contain multiple example sentences on the same line
- or continue across lines without a bullet on the second sentence

Parsing rule:

- strip leading bullet if present
- split on `・`
- also split on sentence boundaries like `。` when another sentence starts after whitespace

Examples:

```text
・幸せな人生を送る。 ・人生経験が豊富な人の話は面白い。
```

becomes:

- `幸せな人生を送る。`
- `人生経験が豊富な人の話は面白い。`

## 4. Relation Lines

Relation lines are compact blocks made of repeated:

```text
<marker> <content>
```

Example:

```text
間 _を送る 会 _経験、_観 類 ―生、生涯
```

This should be segmented into:

- `間 _を送る`
- `会 _経験、_観`
- `類 ―生、生涯`

When relation content uses placeholder marks such as `_`, `＿`, `～`, or `〜`, replace them with the current entry headword after segmentation.
If multiple placeholder marks appear consecutively, such as `__がある` or `高__`, treat the whole run as one slot and insert the headword once.

Example:

```text
88 しゅうにゅう 収入
問 __があるのない、__を得る
答 臨時__、__源、高__
```

should parse relation content as:

- `収入があるのない`
- `収入を得る`
- `臨時収入`
- `収入源`
- `高収入`

### 4.1 Important Rule

Preserve the exact OCR marker.

Do not throw away:

- `間`
- `会`
- `台`
- `類`
- `対`
- `関`
- `問`
- `答`
- `☐`
- `☑`
- `■`

Even if we normalize them later, the raw marker should remain in structured data as `marker`.

### 4.2 Normalized Interpretation

The OCR-visible marker and the normalized relation meaning are different concepts.

Recommended output fields:

- `marker`: raw OCR-visible marker
- `label_jp`: normalized Japanese relation label
- `type`: normalized machine label

Suggested mapping:

| marker | normalized `label_jp` | normalized `type` |
| --- | --- | --- |
| `類` | `類` | `synonym` |
| `対` | `対` | `antonym` |
| `関` | `関` | `related` |
| `連` | `連` | `collocation` |
| `合` | `合` | `compound` |
| `慣` | `慣` | `set_phrase` |
| `問` | `問` | `prompt` |
| `答` | `答` | `answer` |

OCR alias markers seen in this book:

- `間` often behaves like `連` or sometimes `関`
- `会` often behaves like `合`
- `台` can be an OCR variant of `合`
- `意` can be an OCR variant in relation lines and must be handled carefully
- `目` sometimes behaves like `合`
- `☐`, `☑`, `■` often introduce relation-like reference material

These alias markers should be preserved as `marker`, then normalized by context.

Markdown emphasis wrappers around relation markers should be stripped before relation detection.

Example:

```text
**台** _場、_禁止、_違反 **間** ガ停車スル
```

should still be parsed as relation blocks.

## 5. Recommended Entry Schema

Use this shape for vocabulary pages:

```json
{
  "id": 1,
  "reading_kana": "じんせい",
  "kanji": "人生",
  "headword_raw": null,
  "type": null,
  "translations": {
    "en": "life",
    "zh": "人生"
  },
  "examples": [],
  "notes": [],
  "relation_blocks": [
    {
      "marker": "間",
      "label_jp": "連",
      "type": "collocation",
      "content": "_を送る",
      "items": ["_を送る"]
    }
  ]
}
```

Optional fields:

- `headword_raw`: keep OCR headword if it contains attached grammar markers like `ガ出勤スル`
- `type`: extracted grammatical pattern such as `ガスル`, `ヲスル`, `ガ(ヲ)スル`
- `senses`: for entries with `①`, `②`, etc.
- `notes`: for comments, caution notes, or OCR leftovers that do not fit other fields

## 5.1 `ガ / ヲ / スル` Is Grammatically Important

The markers `ガ`, `ヲ`, and `スル` are not decoration.

They are strong grammatical indicators and should be preserved explicitly in structured data.

From the notation legend in the book:

- `ガ` marks an intransitive-like verbal pattern
- `ヲ` marks a transitive-like verbal pattern
- `スル` shows that the noun participates in a `する` verbal construction

Examples:

- `ガ出勤スル`
- `ヲ受験(ヲ)スル`
- `ガ味方(ヲ)スル`
- `ガ苦労スル`

These should not be flattened away during parsing.

### 5.1.1 Parsing Recommendation

If the OCR headword contains attached grammar markers, preserve:

- the raw notation
- the extracted noun/headword
- the grammatical markers
- the normalized `する`-pattern when recoverable

Recommended shape:

```json
{
  "kanji": "味方",
  "headword_raw": "ガ味方(ヲ)スル",
  "type": "ガ(ヲ)スル",
  "verb_behavior": {
    "has_suru_form": true,
    "case_markers": ["ガ", "ヲ"],
    "notes": [
      "ガ indicates intransitive-like behavior",
      "ヲ indicates transitive-like behavior"
    ],
    "normalized_suru_patterns": [
      "味方をする"
    ]
  }
}
```

### 5.1.2 Why This Matters

These markers help recover usage, not just meaning.

For example:

```text
13 みかた ガ味方(ヲ)スル
friend, supporter; side ／朋友，伙伴／ 내 편，편들
・「何があっても、私はあなたの味方です」
・私と弟がけんかすると、母はいつも弟｛の／に｝味方をする。
間 _になる・_をする
対 敵
```

This tells us:

- the headword is `味方`
- it has a `する` verbal usage
- `味方をする` is an important normalized usage pattern
- `ガ` and `ヲ` are grammar cues and should be preserved in the parse

### 5.1.3 Minimum Rule

When a headword contains any of:

- `ガ`
- `ヲ`
- `スル`
- `(ヲ)スル`

the parser should:

1. keep the original form in `headword_raw`
2. extract a cleaned noun/headword into `kanji`
3. store a grammatical pattern field such as `type`
4. avoid discarding these markers as OCR noise unless there is strong evidence they are wrong

The same rule applies when the marked headword appears on a second heading line such as `## ガ突き当たる` or `## 9引っ張る`.

## 6. Multi-Sense Entries

Some entries have numbered senses:

```text
2 にんげん 人間 human being, man; personality／人，人类／인간，인종
①・人間は皆、平等である。 ・この殺人犯に人間らしい心はないのだろうか。
会 _らしい 類 人 間 人類
②・あんな大きな失敗をした社員を首にしない、うちの社長は人間ができている。
・どんな人間かわからない人を信用してはいけない。
類 人物 間 人間ができている
```

Recommended parse:

- entry-level shared header
- `senses[]`
- each sense has:
  - `label`
  - `content` or `examples`
  - `relation_blocks`

## 7. Exercise Page Format

Exercise pages have a different grammar:

```text
Unit 01 名詞 A
1～50
練習問題 I
Step 1 2 3 4

I （ ）に助詞を書きなさい。
1. ...
2. ...

Ⅱ 「する」が付く言葉に○を付けなさい。
敵 味方 まね ...
```

Recommended exercise schema:

```json
{
  "metadata": {
    "unit_header": "Unit 01 名詞 A",
    "range": "1～50",
    "exercise_title": "練習問題 I",
    "step_header": "Step 1 2 3 4"
  },
  "sections": [
    {
      "id": "I",
      "instruction": "（ ）に助詞を書きなさい。",
      "questions": []
    },
    {
      "id": "Ⅱ",
      "instruction": "「する」が付く言葉に○を付けなさい。",
      "term_list": []
    }
  ]
}
```

## 8. Parsing Strategy

Use this order:

1. classify page type
2. strip image links and pure page-number lines
3. extract common metadata
4. split vocabulary pages into entry blocks using leading entry numbers
5. parse each block in this order:
   - header
   - translation block
   - sense markers
   - examples
   - relation lines
   - residual notes

This order matters because relation markers and translations can be misread if you parse free-form.

## 9. Heuristics That Work Well

### 9.1 Header Detection

Strong signal:

```text
^\d+\s+
```

plus:

- next token is usually kana
- later segment often contains multilingual translations

### 9.2 Translation Detection

Strong signal:

- line contains 2 or 3 translation segments separated by `／`
- first segment often contains Latin letters when English is present
- English glosses may begin with a parenthetical qualifier such as `(married) couple`
- OCR may mix `/` and `／`, so translation splitting should use the earliest valid separator, not a fixed separator preference

### 9.3 Relation Detection

Strong signal:

- line contains short label markers in predictable positions
- markers are followed by compact lexical content, not full prose paragraphs

Important:

- do not match marker-like characters everywhere in a line
- only match them in relation-label positions
- strip markdown emphasis such as `**台**` or `**間**` before testing the line

## 10. Common OCR Problems

### 10.1 Marker Confusion

OCR sometimes confuses relation labels:

- `連` -> `間`
- `合` -> `会`
- `関` or `連` -> `意`
- other small labels may drift

Solution:

- preserve raw `marker`
- normalize using context

### 10.2 Headword Noise

Examples:

- `ヨラ尊敬スル`
- `ガ出世(ヲ)スル`

Solution:

- preserve raw form in `headword_raw`
- extract normalized surface into `kanji`
- store grammatical tail separately in `type`

### 10.3 Example/Relation Boundary Drift

OCR may merge:

- an example sentence with a following relation line
- a translation line with an example line

Solution:

- parse in layers
- prioritize translation detection before example detection
- prioritize relation-marker segmentation after example splitting

## 11. Minimum Output Standard

For each parsed vocabulary entry, the parser should aim to recover at least:

- `id`
- `reading_kana`
- `kanji`
- `translations`
- `examples`
- `relation_blocks`

If something is uncertain:

- keep raw text in `notes`
- do not silently discard it

## 12. Practical Rule For This Project

When OCR text looks like this:

```text
<id> <reading> <surface> <en>／<zh>／<ko>
<examples>
<marker blocks>
```

parse it directly into:

- header fields
- translation fields
- example list
- relation block list

This is the default parse model for the early vocabulary pages of this book.
