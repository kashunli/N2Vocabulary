import { useEffect, useRef, useState } from "react";

import { PlaybackSettingsModal } from "./features/player/PlaybackSettingsModal";
import { RailPlayer } from "./features/player/RailPlayer";
import { useStudyKeyboardShortcuts } from "./features/player/useStudyKeyboardShortcuts";
import { useStudyPlayback } from "./features/player/useStudyPlayback";
import {AccountControls} from "./features/study/AccountControls";
import { StudyHeader } from "./features/study/StudyHeader";
import { StudyWallView } from "./features/study/StudyWallView";
import { useStudyActions } from "./features/study/useStudyActions";
import { useStudyCatalog } from "./features/study/useStudyCatalog";
import { useStudyEntries } from "./features/study/useStudyEntries";
import { readStudyFocus } from "./features/study/studyFocus";
import { readStudyViewState, saveStudyViewState } from "./features/study/studyViewState.mjs";
import { useStudyState } from "./features/study/useStudyState";
import { markStatusOf } from "./features/study/markStatus";
import type { ReviewSession } from "./features/study/studyStateTypes";
import type { FilterState } from "./features/study/studyTypes";
import type { Entry } from "./types";

function StudyApp({store, snapshot}: ReturnType<typeof useStudyState>) {
  const [initialView] = useState(() => readStudyViewState());
  const [selectedBook, setSelectedBook] = useState(() => initialView.selectedBook || readStudyFocus()?.bookCode || "N2");
  const [selectedUnit, setSelectedUnit] = useState<number | null>(() => initialView.selectedUnit ?? null);
  const [filterState, setFilterState] = useState<FilterState>(() => initialView.filterState || "all");
  const [entries, setEntries] = useState<Entry[]>([]);
  const [entriesLoading, setEntriesLoading] = useState(false);
  const [blurred, setBlurred] = useState(false);
  const [listVisible, setListVisible] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [reviewSession, setReviewSession] = useState<ReviewSession>();
  const reviewCompletionInFlight = useRef(new Set<string>());

  useEffect(() => {
    if (filterState !== "review") setReviewSession(undefined);
    reviewCompletionInFlight.current.clear();
  }, [filterState, selectedBook, selectedUnit]);

  const {
    activeEntry: playbackEntry,
    activeIndex: playbackIndex,
    activePhase,
    addSequenceStep,
    autoAdvance,
    cancelSilence,
    canNext,
    canPrevious,
    changePlaybackMode,
    changeSequenceStep,
    moveSequenceStep,
    removeSequenceStep,
    handlePlaybackEnd,
    handlePlayingChange,
    moveClip: movePlaybackClip,
    pauseRequest,
    playbackActive,
    playbackMode,
    playbackRunMode,
    playRequest,
    replayFocused,
    replayRequest,
    resetPlaybackSettings,
    resetPosition,
    selectEntry: selectPlaybackEntry,
    selectPhase,
    sequence,
    target,
    togglePlaybackRunMode,
    togglePlayback,
  } = useStudyPlayback({
    entries,
    onCompleteCard: entry => {
      if (filterState !== "review") {
        void store.recordStudyCompleted(entry).catch(error => setStatus(error instanceof Error ? error.message : "Could not save study playback."));
        return;
      }
      const session = reviewSession;
      const expectedDueAt = session?.expectedDueAtByItemUuid[entry.item_uuid];
      if (!expectedDueAt || !session || session.completedByItemUuid[entry.item_uuid] || reviewCompletionInFlight.current.has(entry.item_uuid)) return;
      reviewCompletionInFlight.current.add(entry.item_uuid);
      void store.completeReview(entry, expectedDueAt).then((result) => {
        const card = result.card;
        const nextDueAt = card?.due_at;
        if (!result.completed || !card || !nextDueAt) {
          setStatus("This review was already completed elsewhere. Re-enter Review to refresh the due list.");
          return;
        }
        setReviewSession(current => current?.scopeKey === session.scopeKey
          ? {...current, completedByItemUuid: {...current.completedByItemUuid, [entry.item_uuid]: {reviewLevel: card.review_level, nextDueAt}}}
          : current);
        setStatus(`${entry.kanji} reviewed. Level ${card.review_level}; next review ${new Date(nextDueAt).toLocaleDateString()}.`);
      }).catch(error => {
        reviewCompletionInFlight.current.delete(entry.item_uuid);
        setStatus(error instanceof Error ? error.message : "Could not save review completion.");
      });
    },
  });
  const activeEntry = playbackEntry;
  const activeIndex = playbackIndex;
  const selectEntry = selectPlaybackEntry;
  const {
    books,
    detail,
    setDetail,
    setStatus,
    status,
    summary,
    units,
  } = useStudyCatalog({activeEntry, selectedBook, selectedUnit, studySnapshot: snapshot});

  // Status messages are transient feedback, not part of the study layout.
  // Removing them after a short pause keeps an error or save confirmation from
  // permanently consuming a row of vertical space above the vocabulary wall.
  useEffect(() => {
    if (!status) return undefined;
    const timeoutId = window.setTimeout(() => setStatus(""), 2900);
    return () => window.clearTimeout(timeoutId);
  }, [setStatus, status]);

  useEffect(() => {
    saveStudyViewState({
      selectedBook,
      selectedUnit,
      filterState,
    });
  }, [filterState, selectedBook, selectedUnit]);

  useEffect(() => {
    if (selectedUnit !== null && units.length && !units.some((unit) => unit.number === selectedUnit)) {
      setSelectedUnit(null);
    }
  }, [selectedUnit, units]);
  const currentBook = books.find((book) => book.code === selectedBook);

  const {
    toggleMark,
  } = useStudyActions({
    activeEntry,
    setDetail,
    setEntries,
    setStatus,
    studyStore: store,
  });

  useStudyEntries({
    filterState,
    resetPosition,
    selectedBook,
    selectedUnit,
    setEntries,
    setEntriesLoading,
    reviewSession,
    setReviewSession,
    setStatus,
    studySnapshot: snapshot,
  });

  useStudyKeyboardShortcuts({
    onBlurToggle: () => setBlurred((current) => !current),
    onMoveClip: movePlaybackClip,
    onReplay: replayFocused,
    onSetSettingsOpen: setSettingsOpen,
    onToggleMark: toggleMark,
    onTogglePlayback: togglePlayback,
    settingsOpen,
  });

  return (
    <main className="react-shell">
      <StudyHeader
        blurred={blurred}
        books={books}
        currentBook={currentBook}
        filterState={filterState}
        selectedBook={selectedBook}
        selectedUnit={selectedUnit}
        summary={summary}
        reviewSessionCount={filterState === "review" ? Object.keys(reviewSession?.expectedDueAtByItemUuid || {}).length : undefined}
        units={units}
        listVisible={listVisible}
        onOpenSettings={() => setSettingsOpen(true)}
        onSelectBook={(book) => { setSelectedBook(book); setSelectedUnit(null); setReviewSession(undefined); }}
        onSelectFilter={(filter) => { setFilterState(filter); if (filter !== "review") setReviewSession(undefined); }}
        onSelectUnit={(unit) => { setSelectedUnit(unit); setReviewSession(undefined); }}
        onToggleBlur={() => setBlurred((current) => !current)}
        onToggleList={() => setListVisible((current) => !current)}
      />
      {status ? <div key={status} className="react-status" role="status" aria-live="polite" aria-atomic="true">{status}</div> : null}

      <div className={`react-content-scroll${blurred ? " is-blurred" : ""}`}>
        <StudyWallView
          activeEntry={activeEntry}
          activeIndex={activeIndex}
          activePhase={activePhase}
          bookCode={activeEntry?.book_code || selectedBook}
          detail={detail}
          entries={entries}
          entriesLoading={entriesLoading}
          listVisible={listVisible}
          onSelectEntry={selectEntry}
          onSelectPhase={selectPhase}
          reviewSession={reviewSession}
        />
      </div>

      <RailPlayer
        target={target}
        autoPlay={autoAdvance}
        isPlaybackActive={playbackActive}
        playbackRunMode={playbackRunMode}
        markStatus={activeEntry ? markStatusOf(activeEntry.mark) : "unmarked"}
        reviewed={!!(activeEntry && reviewSession?.completedByItemUuid[activeEntry.item_uuid])}
        onToggleMark={toggleMark}
        onPlayingChange={handlePlayingChange}
        onCancelSilence={cancelSilence}
        playRequest={playRequest}
        replayRequest={replayRequest}
        pauseRequest={pauseRequest}
        onEnded={handlePlaybackEnd}
        onTogglePlayback={togglePlayback}
        onTogglePlaybackRunMode={togglePlaybackRunMode}
        onReplay={replayFocused}
        onPrevious={() => movePlaybackClip(-1)}
        onNext={() => movePlaybackClip(1)}
        canPrevious={canPrevious}
        canNext={canNext}
      />

      {settingsOpen ? <PlaybackSettingsModal
        playbackMode={playbackMode}
        playbackRunMode={playbackRunMode}
        sequence={sequence}
        onChangePlaybackMode={changePlaybackMode}
        onChangeSequenceStep={changeSequenceStep}
        onAddSequenceStep={addSequenceStep}
        onMoveSequenceStep={moveSequenceStep}
        onRemoveSequenceStep={removeSequenceStep}
        onTogglePlaybackRunMode={togglePlaybackRunMode}
        onClose={() => setSettingsOpen(false)}
        onReset={resetPlaybackSettings}
      /> : null}
    </main>
  );
}

export function App() {
  const studyState = useStudyState();
  if (!studyState.ready) return <main className="react-shell"><p className="react-empty">Loading study state…</p></main>;
  return <><AccountControls state={studyState} /><StudyApp key={studyState.session?.user.id ?? "guest"} {...studyState} /></>;
}
