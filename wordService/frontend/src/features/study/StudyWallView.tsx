import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { SentenceExplanation } from "../explanation/SentenceExplanation";
import type { PlaybackPhase } from "../player/playbackSettings";
import type { Entry } from "../../types";
import { markStatusOf } from "./markStatus";
import { MeaningDisplay } from "./MeaningDisplay";
import { WordDisplay } from "./WordDisplay";
import type { ReviewSession } from "./studyStateTypes";

interface StudyWallViewProps {
  activeEntry?: Entry;
  activeIndex: number;
  activePhase: PlaybackPhase;
  bookCode: string;
  entries: Entry[];
  entriesLoading: boolean;
  emptyMessage?: string;
  listVisible: boolean;
  onSelectEntry: (index: number) => void;
  onSelectPhase: (phase: PlaybackPhase) => void;
  reviewSession?: ReviewSession;
}

export function StudyWallView({
  activeEntry,
  activeIndex,
  activePhase,
  bookCode,
  entries,
  entriesLoading,
  emptyMessage = "Loading vocabulary…",
  listVisible,
  onSelectEntry,
  onSelectPhase,
  reviewSession,
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
    <div className="react-layout" ref={layoutRef} style={{gridTemplateColumns: listVisible ? `${listWidth}px 12px minmax(0, 1fr)` : "minmax(0, 1fr)"}}>
      {listVisible ? <section ref={listRef} className="react-list" aria-label="Vocabulary playback list">
        {entries.length ? entries.map((entry, index) => {
          const reviewCompleted = reviewSession?.completedByItemUuid[entry.item_uuid];
          const status = markStatusOf(entry.mark);
          const statusLabel = [status === "known" ? "Known" : status === "flagged" ? "Flagged" : "", reviewCompleted ? "Reviewed" : ""].filter(Boolean).join(", ");
          const statusIcon = status === "known" ? "✓" : status === "flagged" ? "⚑" : reviewCompleted ? "✓" : "";
          return <button key={entry.entry_id} ref={index === activeIndex ? activeRef : null} className={`${index === activeIndex ? "is-active " : ""}${reviewCompleted ? " is-reviewed" : ""} status-${status}`} aria-label={`${entry.kanji}${statusLabel ? `, ${statusLabel}` : ""}`} aria-current={index === activeIndex ? "true" : undefined} onClick={() => onSelectEntry(index)}><span className="react-row-kanji">{entry.kanji}</span>{statusLabel ? <span className="react-row-status" aria-label={statusLabel} title={statusLabel}>{statusIcon}</span> : null}</button>;
        }) : entriesLoading ? <p className="react-empty">{emptyMessage}</p> : <p className="react-empty">No words match the current filters.</p>}
      </section> : null}
      {listVisible ? <button className="react-divider" type="button" role="separator" aria-orientation="vertical" aria-label="Adjust playback list width" aria-valuemin={220} aria-valuemax={620} aria-valuenow={listWidth} tabIndex={0} onPointerDown={(event) => { event.preventDefault(); event.currentTarget.setPointerCapture(event.pointerId); setDraggingDivider(true); }} onKeyDown={(event) => { if (event.key === "ArrowLeft") setListWidth((value) => Math.max(220, value - (event.shiftKey ? 50 : 20))); else if (event.key === "ArrowRight") setListWidth((value) => Math.min(620, value + (event.shiftKey ? 50 : 20))); else return; event.preventDefault(); }}> </button> : null}
      <section ref={currentRef} className="react-current" aria-live="polite" aria-label="Current vocabulary item">
        {activeEntry ? <>
          <div className="react-word-summary">
            <h2>
              <button
                type="button"
                className="react-word-trigger"
                onClick={() => onSelectPhase("word")}
                disabled={!activeEntry.word_audio_url}
                aria-current={activePhase === "word" ? "true" : undefined}
                aria-label={`Play word audio: ${activeEntry.kanji}`}
                title="Play word audio"
              >
                <WordDisplay word={activeEntry.kanji} reading={activeEntry.reading} />
              </button>
            </h2>
            <MeaningDisplay meaningEn={activeEntry.meaning_en} meaningZh={activeEntry.meaning_zh} />
          </div>
          {reviewSession?.completedByItemUuid[activeEntry.item_uuid] ? <p className="react-review-completed">Reviewed · level {reviewSession.completedByItemUuid[activeEntry.item_uuid].reviewLevel} · next {new Date(reviewSession.completedByItemUuid[activeEntry.item_uuid].nextDueAt).toLocaleDateString()}</p> : null}
          {activeEntry.sentence ? <div className="react-sentence">
              <button
                type="button"
                className="react-sentence-trigger"
                onClick={() => onSelectPhase("sentence")}
                disabled={!activeEntry.sentence_audio_url}
                aria-current={activePhase === "sentence" ? "true" : undefined}
                aria-label="Play sentence audio"
                title="Play sentence audio"
              >
                <strong>{activeEntry.sentence}</strong>
              </button>
            </div> : null}
          {activeEntry.explanation_md ? <SentenceExplanation value={activeEntry.explanation_md} /> : null}
        </> : <p className="react-empty">{emptyMessage}</p>}
      </section>
    </div>
  );
}
