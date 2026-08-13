import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { SentenceExplanation } from "../explanation/SentenceExplanation";
import { SourceMetadata } from "../explanation/SourceMetadata";
import type { PlaybackPhase } from "../player/playbackSettings";
import type { Entry } from "../../types";
import { unitLabel } from "./unitLabel";
import { MeaningDisplay } from "./MeaningDisplay";
import { WordDisplay } from "./WordDisplay";

interface StudyWallViewProps {
  activeEntry?: Entry;
  activeIndex: number;
  activePhase: PlaybackPhase;
  bookCode: string;
  coveredEntryIds: ReadonlySet<number>;
  detail?: Entry;
  entries: Entry[];
  entriesLoading: boolean;
  onSelectEntry: (index: number) => void;
  onSelectPhase: (phase: PlaybackPhase) => void;
  onToggleMark: (key: "known" | "flagged") => void | Promise<void>;
  onToggleSentenceStar: () => void | Promise<void>;
}

export function StudyWallView({
  activeEntry,
  activeIndex,
  activePhase,
  bookCode,
  coveredEntryIds,
  detail,
  entries,
  entriesLoading,
  onSelectEntry,
  onSelectPhase,
  onToggleMark,
  onToggleSentenceStar,
}: StudyWallViewProps) {
  const [listWidth, setListWidth] = useState(320);
  const [draggingDivider, setDraggingDivider] = useState(false);
  const activeRef = useRef<HTMLButtonElement | null>(null);
  const layoutRef = useRef<HTMLDivElement | null>(null);
  const listRef = useRef<HTMLElement | null>(null);
  const currentRef = useRef<HTMLElement | null>(null);

  useLayoutEffect(() => {
    const list = listRef.current;
    const active = activeRef.current;
    if (!list || !active) return;

    // Advancing playback is a queue step, so keep the list still while the
    // next row is already visible. Adjust only this pane when the row crosses
    // an edge; scrollIntoView can also move ancestors and reset the list.
    const listBounds = list.getBoundingClientRect();
    const activeBounds = active.getBoundingClientRect();
    if (activeBounds.bottom > listBounds.bottom) {
      list.scrollTop += activeBounds.bottom - listBounds.bottom;
    } else if (activeBounds.top < listBounds.top) {
      list.scrollTop -= listBounds.top - activeBounds.top;
    }
  }, [activeEntry?.entry_id]);

  useLayoutEffect(() => {
    const current = currentRef.current;
    if (!current) return;
    // A long explanation can leave the detail pane scrolled down. Reset it
    // before the newly focused word is painted so its heading cannot remain
    // hidden above the pane when playback advances.
    current.scrollTop = 0;
    current.scrollLeft = 0;
  }, [activeEntry?.entry_id, bookCode]);

  useEffect(() => {
    if (!draggingDivider) return undefined;
    const move = (event: PointerEvent) => {
      const left = layoutRef.current?.getBoundingClientRect().left || 0;
      setListWidth(Math.min(620, Math.max(220, Math.round(event.clientX - left))));
    };
    const stop = () => setDraggingDivider(false);
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop, {once: true});
    window.addEventListener("pointercancel", stop, {once: true});
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
    };
  }, [draggingDivider]);

  return (
    <div className="react-layout" ref={layoutRef} style={{gridTemplateColumns: `${listWidth}px 12px minmax(0, 1fr)`}}>
      <section ref={listRef} className="react-list" aria-label="Vocabulary playback list">
        {entriesLoading ? <p className="react-empty">Loading vocabulary…</p> : entries.length ? entries.map((entry, index) => <button key={entry.entry_id} ref={index === activeIndex ? activeRef : null} className={`${index === activeIndex ? "is-active " : ""}${coveredEntryIds.has(entry.entry_id) ? "is-covered" : ""}`} aria-current={index === activeIndex ? "true" : undefined} onClick={() => onSelectEntry(index)}><span className="react-row-index">{String(index + 1).padStart(3, "0")}</span><span className="react-row-kanji">{entry.kanji}</span><span className="react-row-status" aria-label={`${entry.mark?.known ? "known" : ""}${entry.mark?.flagged ? " flagged" : ""}`}>{entry.mark?.known ? "✓" : ""}{entry.mark?.flagged ? " ⚑" : ""}</span></button>) : <p className="react-empty">No words match the current filters.</p>}
      </section>
      <button className="react-divider" type="button" role="separator" aria-orientation="vertical" aria-label="Adjust playback list width" aria-valuemin={220} aria-valuemax={620} aria-valuenow={listWidth} tabIndex={0} onPointerDown={(event) => { event.preventDefault(); event.currentTarget.setPointerCapture(event.pointerId); setDraggingDivider(true); }} onKeyDown={(event) => { if (event.key === "ArrowLeft") setListWidth((value) => Math.max(220, value - (event.shiftKey ? 50 : 20))); else if (event.key === "ArrowRight") setListWidth((value) => Math.min(620, value + (event.shiftKey ? 50 : 20))); else return; event.preventDefault(); }}> </button>
      <section ref={currentRef} className={`react-current${activeEntry && coveredEntryIds.has(activeEntry.entry_id) ? " is-covered" : ""}`} aria-live="polite" aria-label="Current vocabulary item">
        {activeEntry ? <>
          <span className="eyebrow">{activeEntry.book_code} #{String(activeEntry.source_index).padStart(3, "0")} · {unitLabel(activeEntry.unit)}</span>
          <h2><WordDisplay word={activeEntry.kanji} reading={activeEntry.reading} /></h2>
          {coveredEntryIds.has(activeEntry.entry_id) ? <p className="react-covered-note">Answers covered. Press Uncover all or Cover all to reveal the study details.</p> : <>
            <MeaningDisplay meaningEn={activeEntry.meaning_en} meaningZh={activeEntry.meaning_zh} />
            <div className="react-current-actions">
              <button type="button" onClick={() => onSelectPhase("word")} className={activePhase === "word" ? "is-selected" : ""}>Word</button>
              <button type="button" onClick={() => onSelectPhase("sentence")} className={activePhase === "sentence" ? "is-selected" : ""} disabled={!activeEntry.sentence_audio_url}>Sentence</button>
              <button type="button" className={activeEntry.mark?.known ? "is-on" : ""} onClick={() => void onToggleMark("known")} aria-pressed={!!activeEntry.mark?.known}>✓ Known</button>
              <button type="button" className={activeEntry.mark?.flagged ? "is-on" : ""} onClick={() => void onToggleMark("flagged")} aria-pressed={!!activeEntry.mark?.flagged}>⚑ Flag</button>
              <button type="button" className={activeEntry.sentence_starred ? "is-on" : ""} onClick={() => void onToggleSentenceStar()} aria-pressed={!!activeEntry.sentence_starred}>{activeEntry.sentence_starred ? "★" : "☆"} Sentence</button>
            </div>
            {detail?.sentence ? <div className="react-sentence"><strong>{detail.sentence}</strong><span>{detail.sentence_translation_en || detail.sentence_translation_zh}</span></div> : null}
            {detail?.source_notes ? <SourceMetadata notes={detail.source_notes} /> : null}
            {detail?.explanation_md ? <SentenceExplanation value={detail.explanation_md} /> : null}
          </>}
        </> : <p className="react-empty">Loading vocabulary…</p>}
      </section>
    </div>
  );
}
