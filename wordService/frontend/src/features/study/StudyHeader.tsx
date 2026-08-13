import type { AudioTarget, BookSummary, UnitSummary, VocabularySummary } from "../../types";
import type { PlaybackRunMode } from "../player/playbackSettings";
import { unitLabel } from "./unitLabel";
import type { FilterState } from "./studyTypes";

export type { FilterState } from "./studyTypes";

interface StudyHeaderProps {
  allVisibleCovered: boolean;
  blurred: boolean;
  books: BookSummary[];
  currentBook?: BookSummary;
  entriesCount: number;
  exportFlaggedAudio: () => void;
  filterState: FilterState;
  isSilencePaused: boolean;
  playbackActive: boolean;
  playbackRunMode: PlaybackRunMode;
  search: string;
  selectedBook: string;
  selectedUnit: number | null;
  showStarred: boolean;
  summary?: VocabularySummary;
  target: AudioTarget | null;
  units: UnitSummary[];
  onOpenSettings: () => void;
  onSearch: (value: string) => void;
  onSelectBook: (book: string) => void;
  onSelectFilter: (filter: FilterState) => void;
  onSelectUnit: (unit: number | null) => void;
  onToggleBlur: () => void;
  onToggleCoverAll: () => void;
  onTogglePlayback: () => void;
  onToggleStarred: () => void;
}

export function StudyHeader({
  allVisibleCovered,
  blurred,
  books,
  currentBook,
  entriesCount,
  exportFlaggedAudio,
  filterState,
  isSilencePaused,
  playbackActive,
  playbackRunMode,
  search,
  selectedBook,
  selectedUnit,
  showStarred,
  summary,
  target,
  units,
  onOpenSettings,
  onSearch,
  onSelectBook,
  onSelectFilter,
  onSelectUnit,
  onToggleBlur,
  onToggleCoverAll,
  onTogglePlayback,
  onToggleStarred,
}: StudyHeaderProps) {
  return (
    <>
      <header className="react-header">
        <div className="react-brand">
          <span className="eyebrow">N2 VOCABULARY · REACT PREVIEW</span>
          <h1>{currentBook?.title || "スタディウォール"}</h1>
          <div className="react-summary-meta">
            {summary ? <><span>{summary.entries} entries</span><span>{summary.units} sections</span><span>{summary.known} known</span><span>{summary.flagged} flagged</span><span>{summary.unmarked} unmarked</span></> : <span>Loading vocabulary…</span>}
          </div>
        </div>
        <div className="react-pickers">
          <label><span>Book</span><select value={selectedBook} onChange={(event) => onSelectBook(event.target.value)}><option value="">Choose book</option>{books.map((book) => <option key={book.code} value={book.code}>{book.code} · {book.title}</option>)}</select></label>
          <label><span>Section</span><select value={selectedUnit ?? ""} onChange={(event) => onSelectUnit(event.target.value ? Number(event.target.value) : null)}><option value="">All sections</option>{units.map((item) => <option key={item.number} value={item.number}>{unitLabel(item)} · {item.entry_count} words</option>)}</select></label>
        </div>
      </header>

      <nav className="react-unit-strip" aria-label="Sections">
        <button type="button" className={selectedUnit === null ? "is-selected" : ""} onClick={() => onSelectUnit(null)}>All</button>
        {units.map((item) => <button type="button" key={item.number} className={selectedUnit === item.number ? "is-selected" : ""} onClick={() => onSelectUnit(item.number)} title={`${item.title} · ${item.entry_count} words`}>{unitLabel(item)}</button>)}
      </nav>

      <section className="react-toolbar" aria-label="Study controls">
        <div className="react-toolbar-search"><input type="search" value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Search kanji, reading, meaning, sentence…" aria-label="Search vocabulary" /></div>
        <div className="react-pill-group" role="group" aria-label="Study state filter">
          {(["all", "unmarked", "known", "flagged"] as FilterState[]).map((filter) => <button type="button" key={filter} className={`${filterState === filter ? "is-selected " : ""}react-pill react-pill-${filter}`} onClick={() => onSelectFilter(filter)}>{filter[0].toUpperCase() + filter.slice(1)}{filter !== "all" && summary ? <small>{summary[filter]}</small> : null}</button>)}
        </div>
        <div className="react-toolbar-actions">
          <button type="button" onClick={onToggleCoverAll} disabled={!entriesCount} aria-pressed={allVisibleCovered}>{allVisibleCovered ? "Uncover all" : "Cover all"}</button>
          <button type="button" onClick={onTogglePlayback} disabled={!target} aria-pressed={playbackActive}>{playbackActive ? "Pause" : isSilencePaused ? "Resume" : playbackRunMode === "single" ? "Play one" : "Play visible"}</button>
          <button type="button" className={showStarred ? "is-selected" : ""} onClick={onToggleStarred} aria-pressed={showStarred}>★ Starred sentences</button>
          <a href="/audio-review.html">Audio text review</a>
          <button type="button" onClick={exportFlaggedAudio} disabled={selectedUnit === null}>Export flagged audio</button>
          <a href="/classic">Classic study wall</a>
          <button type="button" onClick={onToggleBlur} aria-pressed={blurred} title="B: blur / reveal the study content">B</button>
          <button type="button" className="react-settings-button" onClick={onOpenSettings} aria-label="Open playback settings" title="Playback settings">⚙</button>
        </div>
      </section>
    </>
  );
}
