import { List } from "@phosphor-icons/react";

import { useI18n, type AppLanguage } from "../../i18n";
import type { BookSummary, UnitSummary, VocabularySummary } from "../../types";
import { unitLabel } from "./unitLabel";
import type { FilterState } from "./studyTypes";

export type { FilterState } from "./studyTypes";

interface StudyHeaderProps {
  blurred: boolean;
  books: BookSummary[];
  currentBook?: BookSummary;
  filterState: FilterState;
  listVisible: boolean;
  reviewSessionCount?: number;
  selectedBook: string;
  selectedUnit: number | null;
  sectionLoading: boolean;
  summary?: VocabularySummary;
  units: UnitSummary[];
  onOpenSettings: () => void;
  onSelectBook: (book: string) => void;
  onSelectFilter: (filter: FilterState) => void;
  onSelectUnit: (unit: number | null) => void;
  onToggleBlur: () => void;
  onToggleList: () => void;
}

function filterCount(summary?: VocabularySummary, reviewSessionCount?: number): (filter: FilterState) => number | undefined {
  return (filter) => {
    switch (filter) {
      case "all": return summary?.entries;
      case "review": return reviewSessionCount ?? summary?.review;
      case "known": return summary?.known;
      case "flagged": return summary?.flagged;
      case "unmarked": return summary?.unmarked;
    }
  };
}

export function StudyHeader({
  blurred,
  books,
  currentBook,
  filterState,
  listVisible,
  reviewSessionCount,
  selectedBook,
  selectedUnit,
  sectionLoading,
  summary,
  units,
  onOpenSettings,
  onSelectBook,
  onSelectFilter,
  onSelectUnit,
  onToggleBlur,
  onToggleList,
}: StudyHeaderProps) {
  const countFor = filterCount(summary, reviewSessionCount);
  const {copy, language, setLanguage} = useI18n();
  return (
    <header className="react-header">
      <div className="react-brand">
        <span className="eyebrow"><span className="brand-seal" aria-hidden="true">印</span><span className="brand-caption">{copy.brandCaption}</span></span>
        <h1>{currentBook?.code || copy.studyWall}</h1>
      </div>
      <div className="react-pickers">
        <label><span>{copy.book}</span><select value={selectedBook} onChange={(event) => onSelectBook(event.target.value)}><option value="">{copy.chooseBook}</option>{books.map((book) => <option key={book.code} value={book.code}>{book.code}</option>)}</select></label>
        <label><span>{copy.section}</span><select disabled={sectionLoading} value={selectedUnit ?? ""} onChange={(event) => onSelectUnit(event.target.value ? Number(event.target.value) : null)}><option value="">{sectionLoading ? copy.loadingSections : copy.allSections}</option>{units.map((item) => <option key={item.number} value={item.number}>{unitLabel(item)} · {copy.wordCount(item.entry_count)}</option>)}</select></label>
      </div>
      <select className="react-filter-select" value={filterState} onChange={(event) => onSelectFilter(event.target.value as FilterState)} aria-label={copy.filterItems}>
        {(["all", "review", "unmarked", "known", "flagged"] as FilterState[]).map((filter) => {
          const count = countFor(filter);
          return <option key={filter} value={filter}>{copy.filterLabel(filter)}{count !== undefined ? ` (${count})` : ""}</option>;
        })}
      </select>
      <div className="react-header-actions">
        <label className="react-language-picker"><span>{copy.languageLabel}</span><select value={language} onChange={(event) => setLanguage(event.target.value as AppLanguage)} aria-label={copy.languageLabel}><option value="en">{copy.english}</option><option value="zh">{copy.chinese}</option></select></label>
        <button type="button" className={blurred ? "is-selected" : ""} onClick={onToggleBlur} aria-pressed={blurred} title={copy.blurStudyContent}>B</button>
        <button type="button" className={`react-list-toggle${listVisible ? " is-selected" : ""}`} onClick={onToggleList} aria-pressed={listVisible} aria-label={listVisible ? copy.hideVocabularyList : copy.showVocabularyList} title={listVisible ? copy.hideVocabularyList : copy.showVocabularyList}><List size={16} weight="bold" /></button>
        <button type="button" className="react-settings-button" onClick={onOpenSettings} aria-label={copy.openPlaybackSettings} title={copy.playbackSettings}>⚙</button>
      </div>
    </header>
  );
}
