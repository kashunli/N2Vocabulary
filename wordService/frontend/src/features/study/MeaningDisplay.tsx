interface MeaningDisplayProps {
  meaningEn?: string;
  meaningZh?: string;
}

/** Keep both learner-facing word meanings visible when both are available. */
export function MeaningDisplay({meaningEn, meaningZh}: MeaningDisplayProps) {
  const english = meaningEn?.trim();
  const chinese = meaningZh?.trim();
  if (!english && !chinese) return null;

  return (
    <p className="react-meaning">
      {english ? <span className="react-meaning-en">{english}</span> : null}
      {english && chinese ? <span aria-hidden="true"> · </span> : null}
      {chinese ? <span className="react-meaning-zh">{chinese}</span> : null}
    </p>
  );
}
