import type { ReactNode } from "react";

const KANJI_RE = /[\u3400-\u4dbf\u4e00-\u9fff]/u;
const KANA_RE = /^[\u3040-\u30ffー・／/（）()\s]+$/u;
const LEADING_GRAMMAR_MARKER_RE = /^[ガヲ]\s*/u;

interface WordDisplayProps {
  word: string;
  reading?: string;
}

/**
 * Keep the word itself in one place and attach furigana to it when the
 * reading is a kana-only annotation. Some source readings contain grammar
 * markers or kanji spellings, which should not be rendered as furigana.
 */
export function WordDisplay({word, reading}: WordDisplayProps): ReactNode {
  const wordText = word.trim();
  const readingText = (reading || "").trim().replace(LEADING_GRAMMAR_MARKER_RE, "");
  const furigana = readingText && readingText !== wordText && !KANJI_RE.test(readingText) && KANA_RE.test(readingText)
    ? readingText
    : "";

  if (!furigana || !KANJI_RE.test(wordText)) return wordText;
  return <ruby className="react-word-ruby">{wordText}<rt>{furigana}</rt></ruby>;
}
