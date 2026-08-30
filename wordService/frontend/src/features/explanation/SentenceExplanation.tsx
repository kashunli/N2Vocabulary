import { MarkdownContent } from "./MarkdownContent";
import { useI18n } from "../../i18n";

interface SentenceExplanationProps {
  sentenceTranslation?: string;
  value: string;
}

/** Keep the explanation visible so it can be read without an extra toggle. */
export function SentenceExplanation({sentenceTranslation, value}: SentenceExplanationProps) {
  const {copy} = useI18n();
  return (
    <section className="react-sentence-explanation" aria-label={copy.sentenceExplanation}>
      <MarkdownContent value={value} omitParagraph={sentenceTranslation} />
    </section>
  );
}
