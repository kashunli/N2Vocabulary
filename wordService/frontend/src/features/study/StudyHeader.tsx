import type { BookSummary, UnitSummary, VocabularySummary } from "../../types";
import { unitLabel } from "./unitLabel";
import type { FilterState } from "./studyTypes";

export type { FilterState } from "./studyTypes";

interface StudyHeaderProps {
  blurred: boolean;
  books: BookSummary[];
  currentBook?: BookSummary;
  exportFlaggedAudio: () => void;
  filterState: FilterState;
  reviewSessionCount?: number;
  search: string;
  selectedBook: string;
  selectedUnit: number | null;
  summary?: VocabularySummary;
  units: UnitSummary[];
  onOpenSettings: () => void;
  onSearch: (value: string) => void;
  onSelectBook: (book: string) => void;
  onSelectFilter: (filter: FilterState) => void;
  onSelectUnit: (unit: number | null) => void;
  onToggleBlur: () => void;
}

export function StudyHeader({
  blurred,
  books,
  currentBook,
  exportFlaggedAudio,
  filterState,
  reviewSessionCount,
  search,
  selectedBook,
  selectedUnit,
  summary,
  units,
  onOpenSettings,
  onSearch,
  onSelectBook,
  onSelectFilter,
  onSelectUnit,
  onToggleBlur,
}: StudyHeaderProps) {
  return (
    <>
      <header className="react-header">
        <div className="react-brand">
          <span className="eyebrow"><span className="brand-seal" aria-hidden="true">印</span>JLPT N2 · VOCABULARY</span>
          <div className="react-title-line">
            <h1>{currentBook?.title || "スタディウォール"}</h1>
            <div className="react-summary-meta">
              {summary ? <><span>{summary.entries} entries</span><span>{summary.units} sections</span><span>{summary.known} known</span><span>{summary.flagged} flagged</span><span>{summary.unmarked} unmarked</span></> : <span>Loading vocabulary…</span>}
            </div>
          </div>
        </div>
        <div className="react-pickers">
          <label><span>Book</span><select value={selectedBook} onChange={(event) => onSelectBook(event.target.value)}><option value="">Choose book</option>{books.map((book) => <option key={book.code} value={book.code}>{book.code} · {book.title}</option>)}</select></label>
          <label><span>Section</span><select value={selectedUnit ?? ""} onChange={(event) => onSelectUnit(event.target.value ? Number(event.target.value) : null)}><option value="">All sections</option>{units.map((item) => <option key={item.number} value={item.number}>{unitLabel(item)} · {item.entry_count} words</option>)}</select></label>
        </div>
      </header>

      <section className="react-toolbar" aria-label="Study controls">
        <div className="react-toolbar-search"><input type="search" value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Search kanji, reading, meaning, sentence…" aria-label="Search vocabulary" /></div>
        <div className="react-pill-group" role="group" aria-label="Study state filter">
          {(["all", "review", "unmarked", "known", "flagged"] as FilterState[]).map((filter) => {
            const count = filter === "review" ? reviewSessionCount ?? summary?.review
              : filter === "known" ? summary?.known
                : filter === "flagged" ? summary?.flagged
                  : filter === "unmarked" ? summary?.unmarked
                    : undefined;
            return <button type="button" key={filter} className={`${filterState === filter ? "is-selected " : ""}react-pill react-pill-${filter}`} onClick={() => onSelectFilter(filter)}>{filter[0].toUpperCase() + filter.slice(1)}{count !== undefined ? <small>{count}</small> : null}</button>;
          })}
        </div>
        <div className="react-toolbar-actions">
          <button type="button" onClick={exportFlaggedAudio} disabled={selectedUnit === null}>Export flagged audio</button>
          <a href="/classic">Classic study wall</a>
          <button type="button" onClick={onToggleBlur} aria-pressed={blurred} title="B: blur / reveal the study content">B</button>
          <button type="button" className="react-settings-button" onClick={onOpenSettings} aria-label="Open playback settings" title="Playback settings">⚙</button>
        </div>
      </section>
    </>
  );
}
