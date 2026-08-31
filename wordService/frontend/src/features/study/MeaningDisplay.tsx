interface MeaningDisplayProps {
  meaningEn?: string;
  meaningZh?: string;
}

/** Keep both learner-facing meanings visible; UI language must not hide content. */
export function MeaningDisplay({meaningEn, meaningZh}: MeaningDisplayProps) {
  const english = meaningEn?.trim();
  const chinese = meaningZh?.trim();
  if (!english && !chinese) return null;

  return (
    <p className="react-meaning">
      {english ? <span className="react-meaning-en" lang="en">{english}</span> : null}
      {english && chinese ? <span aria-hidden="true"> · </span> : null}
      {chinese ? <span className="react-meaning-zh" lang="zh-CN">{chinese}</span> : null}
    </p>
  );
}
