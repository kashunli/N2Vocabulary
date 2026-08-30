import { useI18n } from "../../i18n";

interface MeaningDisplayProps {
  meaningEn?: string;
  meaningZh?: string;
}

/** Show the meaning for the selected UI language, with a safe fallback. */
export function MeaningDisplay({meaningEn, meaningZh}: MeaningDisplayProps) {
  const {language, selectText} = useI18n();
  const english = meaningEn?.trim();
  const chinese = meaningZh?.trim();
  const meaning = selectText(meaningEn, meaningZh);
  if (!meaning) return null;
  const displayedLanguage = language === "zh"
    ? chinese ? "zh-CN" : "en"
    : english ? "en" : "zh-CN";

  return (
    <p className="react-meaning">
      <span className={`react-meaning-${displayedLanguage === "zh-CN" ? "zh" : "en"}`} lang={displayedLanguage}>{meaning}</span>
    </p>
  );
}
