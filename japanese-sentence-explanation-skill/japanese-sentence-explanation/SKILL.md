---
name: japanese-sentence-explanation
description: "explain, analyze, or break down japanese sentences and phrases for joseph. use whenever joseph submits japanese text for translation, grammar analysis, sentence explanation, or phrase breakdown. always use this skill instead of default behavior for japanese sentence explanations, especially when joseph wants nuance, literal meaning, semantic drift, or jlpt-tagged grammar notes."
---
 
# Japanese Sentence Explanation Skill
 
Joseph is a Chinese native speaker at the N2–N3 boundary with strong kanji literacy. He learns best from concrete grammar tied to the sentence at hand, with literal meanings and semantic drift notes.
 
## Output format
 
Bold natural English translation, then a horizontal rule, then a bullet list with no section header. Markdown only.
 
Bullet shapes:
- **term（よみ）** — definition [JLPT Nx]
- **verb（よみ）** — definition; 他動詞/自動詞 ↔ counterpart verb [JLPT Nx]
- **~grammar** — function and nuance in this sentence [JLPT Nx]
Use symbols freely to show relations and save words: "=>" for result/implication, "↔" for contrast or counterpart, "≈" for rough equivalence, ":" to introduce explanation.
 
## Style
 
- Concise. Omit obvious syntactic labels (e.g. don't say "sentence-level adverb" when "adverb" suffices, or skip the label entirely if self-evident).
- Bold the term being explained: **一般（いっぱん）に**
- Use italics for literal glosses: *"one who has accumulated years"*
- Break long bullets at a natural boundary (=> or ↔) rather than running on.
- Anchor every note to the actual sentence; no generic textbook filler.
- Prefer nuance over enumeration.
## What to include
 
- Notable non-N5 vocabulary and grammar
- Kanji + inline furigana whenever a standard kanji spelling exists, even for words usually written in kana (威張（いば）る, 勿論（もちろん）)
- 和語: literal meaning and semantic drift
- 漢語: comment only when Japanese usage meaningfully differs from modern Chinese
- Flag false friends for Chinese readers (のに, らしい, the two そうだ, etc.)
## What to skip
 
- N5 vocabulary and grammar (see exceptions below)
- Kanji component breakdowns
- Sino-Japanese compounds identical or near-identical to Chinese
- Chunk breakdown tables, polite/plain variants, simpler alternatives, conjugation tables, summary sections
## N5 exceptions
 
Explain an N5 item if Joseph asks, if it functions in a non-basic way, or if it interacts with higher-level grammar that would otherwise be unclear. Keep it brief.
 
## Adversative passive (迷惑の受身)
 
Flag explicitly when present: subject is framed as inconvenienced party — no direct Chinese equivalent.
