---
name: user_japanese_explanation_preference
description: Joseph's preferred format for Japanese sentence explanations — used when updating Anki card explanations
type: feedback
---

**Rule:** When generating or updating explanations for Japanese example sentences, use the `japanese-sentence-explanation` skill format:
1. **Bold English translation** on the first line
2. Horizontal rule `---`
3. Bullet list of vocabulary + grammar items (no section header between translation and bullets)

Each bullet: **word（よみ）** — definition. Usage notes. [JLPT Nx]
- Show kanji form even for words commonly written in kana (いばる → 威張（いば）る)
- For verbs: always state 他動詞/自動詞 and give the counterpart verb
- Include JLPT level labels
- Include literal meaning and semantic drift notes
- Flag adversative passives, wago vs kango notes, Chinese false friends

**Skip:** kanji component breakdowns, sino-Japanese compounds identical to Chinese, chunk tables, polite/plain variants, simpler alternatives, closing summaries.

**Why:** Joseph is a Chinese native speaker at N2-N3 level. He already knows kanji structure from Chinese literacy and doesn't need basic breakdowns. He learns best through concrete grammar anchored to the sentence, literal meanings, and semantic drift notes.

**How to apply:** Use this format for all new Anki explanation updates and any sentence explanation requests.
