import { MarkdownContent } from "./MarkdownContent";

interface SentenceExplanationProps {
  value: string;
}

/** Keep the explanation visible so it can be read without an extra toggle. */
export function SentenceExplanation({value}: SentenceExplanationProps) {
  return (
    <section className="react-sentence-explanation" aria-label="Sentence explanation">
      <h3>Sentence explanation</h3>
      <MarkdownContent value={value} />
    </section>
  );
}
