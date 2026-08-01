import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import {
  exportUnitFlaggedAudio,
  getBooks,
  getEntries,
  getEntry,
  getStarredSentences,
  getSummary,
  getUnits,
  updateExampleStar,
  updateMark,
} from "./api";
import { MarkdownContent } from "./features/explanation/MarkdownContent";
import { PlaybackSettingsModal } from "./features/player/PlaybackSettingsModal";
import { RailPlayer } from "./features/player/RailPlayer";
import { useStudyPlayback } from "./features/player/useStudyPlayback";
import { StarredView } from "./features/study/StarredView";
import { StudyHeader, type FilterState } from "./features/study/StudyHeader";
import { unitLabel } from "./features/study/unitLabel";
import type {
  BookSummary,
  Entry,
  StarredSentence,
  UnitSummary,
  VocabularySummary,
} from "./types";

export function App() {
  const [books, setBooks] = useState<BookSummary[]>([]);
  const [selectedBook, setSelectedBook] = useState("N2");
  const [summary, setSummary] = useState<VocabularySummary>();
  const [units, setUnits] = useState<UnitSummary[]>([]);
  const [selectedUnit, setSelectedUnit] = useState<number | null>(null);
  const [filterState, setFilterState] = useState<FilterState>("all");
  const [search, setSearch] = useState("");
  const [entries, setEntries] = useState<Entry[]>([]);
  const [entriesLoading, setEntriesLoading] = useState(false);
  const [detail, setDetail] = useState<Entry>();
  const [listWidth, setListWidth] = useState(320);
  const [draggingDivider, setDraggingDivider] = useState(false);
  const [coveredEntryIds, setCoveredEntryIds] = useState<Set<number>>(() => new Set());
  const [blurred, setBlurred] = useState(false);
  const [showStarred, setShowStarred] = useState(false);
  const [starredSentences, setStarredSentences] = useState<StarredSentence[]>([]);
  const [selectedStarredKey, setSelectedStarredKey] = useState<string>();
  const [status, setStatus] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const activeRef = useRef<HTMLButtonElement | null>(null);
  const layoutRef = useRef<HTMLDivElement | null>(null);
  const currentRef = useRef<HTMLElement | null>(null);
  const {
    activeEntry,
    activeIndex,
    activePhase,
    autoAdvance,
    canNext,
    canPrevious,
    changePlaybackMode,
    changePostSentenceSilence,
    changePostWordSilence,
    handlePlaybackEnd,
    handlePlayingChange,
    isSilencePaused,
    isSilencePlaying,
    moveClip,
    pauseRequest,
    playbackActive,
    playbackMode,
    postSentenceSilence,
    postWordSilence,
    playRequest,
    replayFocused,
    replayRequest,
    resetPlaybackSettings,
    resetPosition,
    selectEntry,
    selectPhase,
    stopPlayback,
    stopRequest,
    target,
    togglePlayback,
  } = useStudyPlayback({entries, showStarred});
  const currentBook = books.find((book) => book.code === selectedBook);
  const selectedStarred = starredSentences.find((item) => (
    `${item.entry_id}:${item.position}` === selectedStarredKey
  ));
  const allVisibleCovered = entries.length > 0 && entries.every((entry) => coveredEntryIds.has(entry.entry_id));

  useEffect(() => {
    getBooks()
      .then((payload) => setBooks(payload.items))
      .catch((error: unknown) => setStatus(error instanceof Error ? error.message : "Could not load books."));
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getSummary(selectedBook), getUnits(selectedBook)])
      .then(([nextSummary, nextUnits]) => {
        if (cancelled) return;
        setSummary(nextSummary);
        setUnits(nextUnits.items);
      })
      .catch((error: unknown) => {
        if (!cancelled) setStatus(error instanceof Error ? error.message : "Could not load sections.");
      });
    return () => { cancelled = true; };
  }, [selectedBook]);

  useEffect(() => {
    let cancelled = false;
    setEntriesLoading(true);
    getEntries(selectedBook, selectedUnit ?? undefined, filterState, search)
      .then((payload) => {
        if (cancelled) return;
        setEntries(payload.items);
        resetPosition(payload.items);
      })
      .catch((error: unknown) => {
        if (!cancelled) setStatus(error instanceof Error ? error.message : "Could not load vocabulary.");
      })
      .finally(() => {
        if (!cancelled) setEntriesLoading(false);
      });
    return () => { cancelled = true; };
  }, [filterState, playbackMode, resetPosition, search, selectedBook, selectedUnit]);

  useEffect(() => {
    if (!activeEntry) {
      setDetail(undefined);
      return undefined;
    }
    let cancelled = false;
    getEntry(activeEntry.entry_id, selectedBook)
      .then((nextDetail) => { if (!cancelled) setDetail(nextDetail); })
      .catch((error: unknown) => { if (!cancelled) setStatus(error instanceof Error ? error.message : "Could not load word details."); });
    return () => { cancelled = true; };
  }, [activeEntry, selectedBook]);

  useEffect(() => {
    if (!showStarred) return undefined;
    let cancelled = false;
    getStarredSentences(selectedBook, selectedUnit ?? undefined)
      .then((payload) => {
        if (cancelled) return;
        setStarredSentences(payload.items);
        setSelectedStarredKey((current) => payload.items.some((item) => `${item.entry_id}:${item.position}` === current)
          ? current
          : payload.items[0] ? `${payload.items[0].entry_id}:${payload.items[0].position}` : undefined);
      })
      .catch((error: unknown) => { if (!cancelled) setStatus(error instanceof Error ? error.message : "Could not load starred sentences."); });
    return () => { cancelled = true; };
  }, [selectedBook, selectedUnit, showStarred]);

  useEffect(() => {
    activeRef.current?.scrollIntoView({behavior: "smooth", block: "center"});
  }, [activeIndex, entries]);

  useLayoutEffect(() => {
    const current = currentRef.current;
    if (!current) return;
    // A long explanation can leave the detail pane scrolled down. Reset it
    // before the newly focused word is painted so its heading cannot remain
    // hidden above the pane when playback advances.
    current.scrollTop = 0;
    current.scrollLeft = 0;
  }, [activeEntry?.entry_id, selectedBook, showStarred]);

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

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const targetElement = event.target;
      const isWaveformInput = targetElement instanceof HTMLElement && !!targetElement.closest(".line-waveform input");
      if (!isWaveformInput && targetElement instanceof HTMLElement && targetElement.closest("input, select, textarea, [contenteditable='true']")) return;
      if (event.repeat) return;
      const key = event.key.toLowerCase();
      if (event.code === "Space") {
        event.preventDefault();
        togglePlayback();
      } else if (event.key === "ArrowRight" || key === "d") {
        event.preventDefault();
        moveClip(1);
      } else if (event.key === "ArrowLeft" || key === "a") {
        event.preventDefault();
        moveClip(-1);
      } else if (key === "r") {
        event.preventDefault();
        replayFocused();
      } else if (key === "b") {
        event.preventDefault();
        setBlurred((current) => !current);
      } else if (key === "f") {
        event.preventDefault();
        void toggleMark("flagged");
      } else if (key === "k" || event.key === "Enter") {
        event.preventDefault();
        void toggleMark("known");
      } else if (event.key === "Escape" && settingsOpen) {
        setSettingsOpen(false);
      }
    };
    document.addEventListener("keydown", onKey, {capture: true});
    return () => document.removeEventListener("keydown", onKey, {capture: true});
  });

  const refreshCatalog = useCallback(async () => {
    const [nextSummary, nextUnits] = await Promise.all([getSummary(selectedBook), getUnits(selectedBook)]);
    setSummary(nextSummary);
    setUnits(nextUnits.items);
  }, [selectedBook]);

  const toggleMark = useCallback(async (key: "known" | "flagged") => {
    if (!activeEntry) return;
    const next = {
      known: !!activeEntry.mark?.known,
      flagged: !!activeEntry.mark?.flagged,
    };
    next[key] = !next[key];
    try {
      await updateMark(activeEntry.entry_id, next, selectedBook);
      setEntries((current) => current.map((entry) => entry.entry_id === activeEntry.entry_id
        ? {...entry, mark: {...entry.mark, ...next}}
        : entry));
      setDetail((current) => current && current.entry_id === activeEntry.entry_id
        ? {...current, mark: {...current.mark, ...next}}
        : current);
      await refreshCatalog();
      setStatus(`${activeEntry.kanji} is ${next[key] ? key : `not ${key}`}.`);
    } catch (error: unknown) {
      setStatus(error instanceof Error ? error.message : "Could not update the study mark.");
    }
  }, [activeEntry, refreshCatalog, selectedBook]);

  const toggleSentenceStar = useCallback(async () => {
    if (!activeEntry) return;
    const position = activeEntry.sentence_position ?? 0;
    try {
      const payload = await updateExampleStar(activeEntry.entry_id, position, !activeEntry.sentence_starred, selectedBook);
      setEntries((current) => current.map((entry) => entry.entry_id === activeEntry.entry_id
        ? {...entry, sentence_starred: payload.starred}
        : entry));
      setDetail((current) => current && current.entry_id === activeEntry.entry_id
        ? {...current, sentence_starred: payload.starred}
        : current);
      setStatus(payload.starred ? "Main sentence starred." : "Main sentence unstarred.");
      if (showStarred) {
        const starred = await getStarredSentences(selectedBook, selectedUnit ?? undefined);
        setStarredSentences(starred.items);
      }
    } catch (error: unknown) {
      setStatus(error instanceof Error ? error.message : "Could not update the sentence star.");
    }
  }, [activeEntry, selectedBook, selectedUnit, showStarred]);

  const toggleCoverAll = useCallback(() => {
    setCoveredEntryIds((current) => {
      const next = new Set(current);
      if (allVisibleCovered) entries.forEach((entry) => next.delete(entry.entry_id));
      else entries.forEach((entry) => next.add(entry.entry_id));
      return next;
    });
  }, [allVisibleCovered, entries]);

  const exportFlaggedAudio = useCallback(async () => {
    if (selectedUnit === null) {
      setStatus("Choose a section before exporting flagged audio.");
      return;
    }
    try {
      const payload = await exportUnitFlaggedAudio(selectedUnit, selectedBook);
      const link = document.createElement("a");
      link.href = payload.audio_url;
      link.download = payload.file_name || "flagged-audio.mp3";
      document.body.appendChild(link);
      link.click();
      link.remove();
      setStatus(`Exported ${payload.word_count} flagged words from ${unitLabel(units.find((item) => item.number === payload.unit))}.`);
    } catch (error: unknown) {
      setStatus(error instanceof Error ? error.message : "Could not export flagged audio.");
    }
  }, [selectedBook, selectedUnit, units]);

  const focusStarredEntry = useCallback((entryId: number) => {
    const index = entries.findIndex((entry) => entry.entry_id === entryId);
    if (index >= 0) {
      setShowStarred(false);
      selectEntry(index, "sentence");
    } else {
      setStatus("The starred sentence is outside the current filtered list. Clear the search or filter to focus it.");
    }
  }, [entries, selectEntry]);

  return (
    <main className="react-shell">
      <StudyHeader
        allVisibleCovered={allVisibleCovered}
        blurred={blurred}
        books={books}
        currentBook={currentBook}
        entriesCount={entries.length}
        exportFlaggedAudio={() => void exportFlaggedAudio()}
        filterState={filterState}
        isSilencePaused={isSilencePaused}
        playbackActive={playbackActive}
        search={search}
        selectedBook={selectedBook}
        selectedUnit={selectedUnit}
        showStarred={showStarred}
        summary={summary}
        target={target}
        units={units}
        onOpenSettings={() => setSettingsOpen(true)}
        onSearch={setSearch}
        onSelectBook={(book) => { setSelectedBook(book); setSelectedUnit(null); setShowStarred(false); }}
        onSelectFilter={(filter) => { setFilterState(filter); setShowStarred(false); }}
        onSelectUnit={setSelectedUnit}
        onToggleBlur={() => setBlurred((current) => !current)}
        onToggleCoverAll={toggleCoverAll}
        onTogglePlayback={togglePlayback}
        onToggleStarred={() => setShowStarred((current) => !current)}
      />
      {status ? <div className="react-status" role="status" aria-live="polite">{status}</div> : null}

      <div className={`react-content-scroll${blurred ? " is-blurred" : ""}`}>
        {showStarred ? <StarredView
          selectedStarred={selectedStarred}
          selectedStarredKey={selectedStarredKey}
          selectedUnit={selectedUnit}
          starredSentences={starredSentences}
          units={units}
          onFocusEntry={focusStarredEntry}
          onSelectStarred={setSelectedStarredKey}
          onSelectUnit={setSelectedUnit}
        /> : <div className="react-layout" ref={layoutRef} style={{gridTemplateColumns: `${listWidth}px 12px minmax(0, 1fr)`}}>
          <section className="react-list" aria-label="Vocabulary playback list">
            {entriesLoading ? <p className="react-empty">Loading vocabulary…</p> : entries.length ? entries.map((entry, index) => <button key={entry.entry_id} ref={index === activeIndex ? activeRef : null} className={`${index === activeIndex ? "is-active " : ""}${coveredEntryIds.has(entry.entry_id) ? "is-covered" : ""}`} aria-current={index === activeIndex ? "true" : undefined} onClick={() => selectEntry(index)}><span className="react-row-index">{String(index + 1).padStart(3, "0")}</span><span className="react-row-kanji">{entry.kanji}</span><span className="react-row-status" aria-label={`${entry.mark?.known ? "known" : ""}${entry.mark?.flagged ? " flagged" : ""}`}>{entry.mark?.known ? "✓" : ""}{entry.mark?.flagged ? " ⚑" : ""}</span></button>) : <p className="react-empty">No words match the current filters.</p>}
          </section>
          <button className="react-divider" type="button" role="separator" aria-orientation="vertical" aria-label="Adjust playback list width" aria-valuemin={220} aria-valuemax={620} aria-valuenow={listWidth} tabIndex={0} onPointerDown={(event) => { event.preventDefault(); event.currentTarget.setPointerCapture(event.pointerId); setDraggingDivider(true); }} onKeyDown={(event) => { if (event.key === "ArrowLeft") setListWidth((value) => Math.max(220, value - (event.shiftKey ? 50 : 20))); else if (event.key === "ArrowRight") setListWidth((value) => Math.min(620, value + (event.shiftKey ? 50 : 20))); else return; event.preventDefault(); }}> </button>
          <section ref={currentRef} className={`react-current${activeEntry && coveredEntryIds.has(activeEntry.entry_id) ? " is-covered" : ""}`} aria-live="polite" aria-label="Current vocabulary item">
            {activeEntry ? <>
              <span className="eyebrow">{activeEntry.book_code} #{String(activeEntry.source_index).padStart(3, "0")} · {unitLabel(activeEntry.unit)}</span>
              <h2>{activeEntry.kanji}</h2>
              {coveredEntryIds.has(activeEntry.entry_id) ? <p className="react-covered-note">Answers covered. Press Uncover all or Cover all to reveal the study details.</p> : <>
                <ruby>{activeEntry.kanji}<rt>{activeEntry.reading}</rt></ruby>
                <p className="react-meaning">{activeEntry.meaning_en || activeEntry.meaning_zh}</p>
                <div className="react-current-actions">
                  <button type="button" onClick={() => selectPhase("word")} className={activePhase === "word" ? "is-selected" : ""}>Word</button>
                  <button type="button" onClick={() => selectPhase("sentence")} className={activePhase === "sentence" ? "is-selected" : ""} disabled={!activeEntry.sentence_audio_url}>Sentence</button>
                  <button type="button" className={activeEntry.mark?.known ? "is-on" : ""} onClick={() => void toggleMark("known")} aria-pressed={!!activeEntry.mark?.known}>✓ Known</button>
                  <button type="button" className={activeEntry.mark?.flagged ? "is-on" : ""} onClick={() => void toggleMark("flagged")} aria-pressed={!!activeEntry.mark?.flagged}>⚑ Flag</button>
                  <button type="button" className={activeEntry.sentence_starred ? "is-on" : ""} onClick={() => void toggleSentenceStar()} aria-pressed={!!activeEntry.sentence_starred}>{activeEntry.sentence_starred ? "★" : "☆"} Sentence</button>
                </div>
                {detail?.sentence ? <div className="react-sentence"><strong>{detail.sentence}</strong><span>{detail.sentence_translation_en || detail.sentence_translation_zh}</span></div> : null}
                {detail?.explanation_md ? <details><summary>Sentence explanation</summary><MarkdownContent value={detail.explanation_md} /></details> : null}
              </>}
            </> : <p className="react-empty">Loading vocabulary…</p>}
          </section>
        </div>}
      </div>

      <RailPlayer
        target={target}
        autoPlay={autoAdvance}
        isPlaybackActive={playbackActive}
        isSilencePlaying={isSilencePlaying}
        onPlayingChange={handlePlayingChange}
        playRequest={playRequest}
        replayRequest={replayRequest}
        pauseRequest={pauseRequest}
        stopRequest={stopRequest}
        onEnded={handlePlaybackEnd}
        onTogglePlayback={togglePlayback}
        onReplay={replayFocused}
        onPrevious={() => moveClip(-1)}
        onNext={() => moveClip(1)}
        onStop={stopPlayback}
        canPrevious={canPrevious}
        canNext={canNext}
      />

      {settingsOpen ? <PlaybackSettingsModal
        playbackMode={playbackMode}
        postSentenceSilence={postSentenceSilence}
        postWordSilence={postWordSilence}
        onChangePlaybackMode={changePlaybackMode}
        onChangePostSentenceSilence={changePostSentenceSilence}
        onChangePostWordSilence={changePostWordSilence}
        onClose={() => setSettingsOpen(false)}
        onReset={resetPlaybackSettings}
      /> : null}
    </main>
  );
}
