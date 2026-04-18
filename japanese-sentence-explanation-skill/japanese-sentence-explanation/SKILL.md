---
name: japanese-sentence-explanation
description: >
  Use this skill whenever Joseph asks to explain, analyse, or break down a Japanese sentence.
  Triggers on any Japanese sentence or phrase submitted for explanation, translation, or grammar analysis.
  Always use this skill — do not rely on default behaviour — when explaining Japanese to Joseph.
---

# Japanese Sentence Explanation Skill

Joseph is a Chinese native speaker studying Japanese at the N2–N3 boundary. He has strong kanji literacy from Chinese and does not need basic character explanations. He learns best through concrete grammar anchored to the sentence at hand, literal meanings, and semantic drift notes.

---

## Output Structure

### 1. Translation
Provide a natural English translation on the first line, in bold.

### 2. Vocabulary & Grammar Section
A single merged section with NO section header — go straight into the bullet list immediately after the translation and the horizontal rule separator. Go through each notable word or grammatical pattern in the sentence. For each entry:

- Give the word in kanji + furigana inline, e.g. 留守（るす）. If the word is commonly written in kana but has a kanji form, always show the kanji form — e.g. いばる → 威張（いば）る, もちろん → 勿論（もちろん）. This helps Joseph understand meaning via the characters.
- Provide a clear dictionary definition
- For verbs: always state transitive (他動詞) or intransitive (自動詞), and give the counterpart verb if one exists — e.g. 届く (intrans.) ↔ 届ける (trans.), 開く (intrans.) ↔ 開ける (trans.)
- For grammar patterns: give a medium-detail explanation of the function and nuance. No conjugation tables.
- Include JLPT level label where applicable (N5–N1)
- Include literal meaning and semantic drift notes where the surface meaning is surprising, has shifted from the original, or where the Japanese usage diverges from the Chinese equivalent

---

## What to Skip

- **Individual kanji component breakdowns** — Joseph is a native Chinese reader and already knows radical/stroke-level structure
- **Sino-Japanese compounds identical or near-identical in Chinese** — e.g. 結婚、動物、友達、問題、電話. Only note these if the Japanese usage or nuance meaningfully differs from Chinese
- **Chunk breakdown table** — do not include a tabular parse of the sentence
- **Polite/plain form variants** — do not show alternate forms of the sentence
- **Simpler alternatives** — do not suggest easier ways to say the same thing
- **Summary section** — do not add a closing summary paragraph

---

## Special Notes

### Adversative Passive (迷惑の受身)
When the sentence contains an adversative/indirect passive — where the grammatical subject is not the direct object of the verb but is framed as the one harmed — flag this explicitly. It has no clean Chinese equivalent and is one of the most distinctively Japanese passive uses.

### Wago vs. Kango
For wago (和語, native Japanese words), literal meanings and semantic drift are especially worth noting since these often have no Chinese parallel. For kango (漢語, sino-Japanese), only comment if the Japanese meaning has drifted from or differs subtly from modern Chinese usage.

### Grammar Patterns with Chinese False Friends
Flag grammar patterns that might be misread by a Chinese speaker due to surface similarity — e.g. のに (concessive, not purpose), らしい (typicality vs. hearsay), そうだ (appearance vs. hearsay).

---

## Example Output Shape

Output is markdown. Bold translation, horizontal rule, then bullet list directly — no section header.

**Translation here.**

---

- **word（よみ）** — definition. Usage note. [JLPT Nx]
- **〜grammarpattern** — explanation of function and nuance. Example of how it works in this sentence. [JLPT Nx]
