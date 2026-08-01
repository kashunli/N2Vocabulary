import { MarkdownContent } from "../explanation/MarkdownContent";
import type { StarredSentence, UnitSummary } from "../../types";
import { unitLabel } from "./unitLabel";

interface StarredViewProps {
  selectedStarred?: StarredSentence;
  selectedStarredKey?: string;
  selectedUnit: number | null;
  starredSentences: StarredSentence[];
  units: UnitSummary[];
  onFocusEntry: (entryId: number) => void;
  onSelectStarred: (key: string) => void;
  onSelectUnit: (unit: number | null) => void;
}

export function StarredView({
  selectedStarred,
  selectedStarredKey,
  selectedUnit,
  starredSentences,
  units,
  onFocusEntry,
  onSelectStarred,
  onSelectUnit,
}: StarredViewProps) {
  return (
    <section className="react-starred-view" aria-label="Starred sentence review">
      <aside className="react-starred-filter">
        <div className="section-label">Section filter</div>
        <button type="button" className={!selectedUnit ? "is-selected" : ""} onClick={() => onSelectUnit(null)}>
          <strong>All sections</strong><span>{starredSentences.length}</span>
        </button>
        {units.map((item) => (
          <button type="button" key={item.number} className={selectedUnit === item.number ? "is-selected" : ""} onClick={() => onSelectUnit(item.number)}>
            <strong>{unitLabel(item)}</strong><span>{starredSentences.filter((sentence) => sentence.unit.number === item.number).length}</span>
          </button>
        ))}
      </aside>
      <section className="react-starred-list-panel">
        <div className="react-starred-heading"><div><span className="eyebrow">SENTENCE REVIEW</span><h2>Starred sentences</h2></div><span>{starredSentences.length} shown</span></div>
        {starredSentences.length ? starredSentences.map((item, index) => {
          const key = `${item.entry_id}:${item.position}`;
          return <button type="button" key={key} className={`react-starred-row${key === selectedStarredKey ? " is-selected" : ""}`} onClick={() => onSelectStarred(key)}><span>{String(index + 1).padStart(2, "0")}</span><strong>{item.text}</strong><small>{item.translation_en || item.translation_zh}</small><em>★</em></button>;
        }) : <p className="react-empty">No starred sentences yet.</p>}
      </section>
      <aside className="react-starred-detail">
        {selectedStarred ? <>
          <span className="eyebrow">{unitLabel(selectedStarred.unit)} · #{selectedStarred.source_index}</span>
          <h2>{selectedStarred.word}</h2>
          <p className="react-starred-sentence">{selectedStarred.text}</p>
          <p>{selectedStarred.translation_en || selectedStarred.translation_zh}</p>
          <p className="react-meaning">{selectedStarred.meaning_en || selectedStarred.meaning_zh}</p>
          {selectedStarred.explanation_md ? <details open><summary>Sentence explanation</summary><MarkdownContent value={selectedStarred.explanation_md} /></details> : null}
          <button type="button" onClick={() => onFocusEntry(selectedStarred.entry_id)}>Focus in study wall</button>
        </> : <p className="react-empty">Pick a starred sentence to review it here.</p>}
      </aside>
    </section>
  );
}
