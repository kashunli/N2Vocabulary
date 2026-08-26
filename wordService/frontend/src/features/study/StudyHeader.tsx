import { List } from "@phosphor-icons/react";

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
  return (
    <header className="react-header">
      <div className="react-brand">
        <span className="eyebrow"><span className="brand-seal" aria-hidden="true">印</span><span className="brand-caption">JLPT N2 · VOCABULARY</span></span>
        <h1>{currentBook?.code || "スタディウォール"}</h1>
      </div>
      <div className="react-pickers">
        <label><span>Book</span><select value={selectedBook} onChange={(event) => onSelectBook(event.target.value)}><option value="">Choose book</option>{books.map((book) => <option key={book.code} value={book.code}>{book.code}</option>)}</select></label>
        <label><span>Section</span><select value={selectedUnit ?? ""} onChange={(event) => onSelectUnit(event.target.value ? Number(event.target.value) : null)}><option value="">All sections</option>{units.map((item) => <option key={item.number} value={item.number}>{unitLabel(item)} · {item.entry_count} words</option>)}</select></label>
      </div>
      <select className="react-filter-select" value={filterState} onChange={(event) => onSelectFilter(event.target.value as FilterState)} aria-label="Filter items">
        {(["all", "review", "unmarked", "known", "flagged"] as FilterState[]).map((filter) => {
          const count = countFor(filter);
          return <option key={filter} value={filter}>{filter[0].toUpperCase() + filter.slice(1)}{count !== undefined ? ` (${count})` : ""}</option>;
        })}
      </select>
      <div className="react-header-actions">
        <button type="button" className={blurred ? "is-selected" : ""} onClick={onToggleBlur} aria-pressed={blurred} title="B: blur / reveal the study content">B</button>
        <button type="button" className={`react-list-toggle${listVisible ? " is-selected" : ""}`} onClick={onToggleList} aria-pressed={listVisible} aria-label={listVisible ? "Hide the vocabulary list" : "Show the vocabulary list"} title={listVisible ? "Hide the vocabulary list" : "Show the vocabulary list"}><List size={16} weight="bold" /></button>
        <button type="button" className="react-settings-button" onClick={onOpenSettings} aria-label="Open playback settings" title="Playback settings">⚙</button>
      </div>
    </header>
  );
}
