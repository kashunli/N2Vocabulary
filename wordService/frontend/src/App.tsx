import { useEffect, useRef, useState } from "react";

import { getUnits } from "./api";
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
import type { Entry, UnitSummary } from "./types";

function StudyApp({store, snapshot}: ReturnType<typeof useStudyState>) {
  const [initialView] = useState(() => readStudyViewState());
  const [selectedBook, setSelectedBook] = useState(() => initialView.selectedBook || readStudyFocus()?.bookCode || "N2");
  const [selectedUnit, setSelectedUnit] = useState<number | null>(() => initialView.selectedUnit ?? null);
  // Book changes are staged until the learner chooses a Section. This keeps a
  // large book switch from replacing the current wall while the picker is
  // still being used to define the next study scope.
  const [pendingBook, setPendingBook] = useState(selectedBook);
  const [pendingUnit, setPendingUnit] = useState<number | null>(selectedUnit);
  const [pendingUnits, setPendingUnits] = useState<UnitSummary[]>([]);
  const [pendingUnitsLoading, setPendingUnitsLoading] = useState(false);
  const [filterState, setFilterState] = useState<FilterState>(() => initialView.filterState || "all");
  const [entries, setEntries] = useState<Entry[]>([]);
  const [entriesLoading, setEntriesLoading] = useState(false);
  const [blurred, setBlurred] = useState(false);
  const [listVisible, setListVisible] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [reviewSession, setReviewSession] = useState<ReviewSession>();
  const reviewCompletionInFlight = useRef(new Set<string>());
  // A next-list run changes the section asynchronously. Remember the target
  // section until its derived entries replace the outgoing visible list.
  const pendingFollowingUnitRef = useRef<number | undefined>(undefined);

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
    changeSequenceStep,
    moveSequenceStep,
    nativeQueue,
    syncNativeQueueItem,
    completeNativeQueue,
    removeSequenceStep,
    handlePlaybackEnd,
    handlePlayingChange,
    moveClip: movePlaybackClip,
    pauseRequest,
    playbackActive,
    playbackRunMode,
    playRequest,
    replayFocused,
    replayRequest,
    requestPlayback,
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
    onFollowingList: () => {
      // "List" means the selected Section. All sections are already one
      // combined list, so there is no following list to jump to.
      if (selectedUnit === null) return false;
      const currentUnitIndex = units.findIndex((unit) => unit.number === selectedUnit);
      const followingUnit = currentUnitIndex >= 0 ? units[currentUnitIndex + 1] : undefined;
      if (!followingUnit) return false;
      pendingFollowingUnitRef.current = followingUnit.number;
      setSelectedUnit(followingUnit.number);
      setReviewSession(undefined);
      return true;
    },
  });
  const activeEntry = playbackEntry;
  const activeIndex = playbackIndex;
  const selectEntry = selectPlaybackEntry;
  const {
    allEntries,
    books,
    contentLoading,
    setStatus,
    status,
    summary,
    units,
  } = useStudyCatalog({selectedBook, selectedUnit, studySnapshot: snapshot});

  useEffect(() => {
    if (pendingBook === selectedBook) {
      setPendingUnits([]);
      setPendingUnitsLoading(false);
      return undefined;
    }

    let cancelled = false;
    setPendingUnitsLoading(true);
    // This request only supplies labels/counts for the next Section picker;
    // the active wall remains on selectedBook until a section is chosen.
    getUnits(pendingBook)
      .then((payload) => {
        if (!cancelled) setPendingUnits(payload.items);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setPendingUnits([]);
          setStatus(error instanceof Error ? error.message : "Could not load sections.");
        }
      })
      .finally(() => {
        if (!cancelled) setPendingUnitsLoading(false);
      });
    return () => { cancelled = true; };
  }, [pendingBook, selectedBook, setStatus]);

  useEffect(() => {
    // Playback can advance to the next section without going through the
    // picker. Keep the staged control value aligned when no book is pending.
    if (pendingBook === selectedBook) setPendingUnit(selectedUnit);
  }, [pendingBook, selectedBook, selectedUnit]);

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
  const pendingBookSummary = books.find((book) => book.code === pendingBook);
  const visibleUnits = pendingBook === selectedBook ? units : pendingUnits;

  const handleSelectBook = (book: string) => {
    if (!book) return;
    setPendingBook(book);
    setPendingUnit(book === selectedBook ? selectedUnit : null);
  };

  const handleSelectUnit = (unit: number | null) => {
    setSelectedBook(pendingBook);
    setSelectedUnit(unit);
    setPendingUnit(unit);
    setReviewSession(undefined);
  };

  const {
    toggleMark,
  } = useStudyActions({
    activeEntry,
    setEntries,
    setStatus,
    studyStore: store,
  });

  useStudyEntries({
    allEntries,
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

  useEffect(() => {
    const pendingUnit = pendingFollowingUnitRef.current;
    if (pendingUnit === undefined || selectedUnit !== pendingUnit) return;
    // Wait for the new derived list, rather than replaying the ending list in
    // the render where the section picker has changed but its rows have not.
    if (!entries.length || entries[0]?.unit.number !== pendingUnit) return;
    pendingFollowingUnitRef.current = undefined;
    requestPlayback();
  }, [entries, requestPlayback, selectedUnit]);

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
        currentBook={pendingBookSummary || currentBook}
        filterState={filterState}
        selectedBook={pendingBook}
        selectedUnit={pendingUnit}
        summary={summary}
        reviewSessionCount={filterState === "review" ? Object.keys(reviewSession?.expectedDueAtByItemUuid || {}).length : undefined}
        units={visibleUnits}
        sectionLoading={pendingBook !== selectedBook && pendingUnitsLoading}
        listVisible={listVisible}
        onOpenSettings={() => setSettingsOpen(true)}
        onSelectBook={handleSelectBook}
        onSelectFilter={(filter) => { setFilterState(filter); if (filter !== "review") setReviewSession(undefined); }}
        onSelectUnit={handleSelectUnit}
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
          entries={entries}
          entriesLoading={contentLoading || entriesLoading}
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
        onToggleMark={toggleMark}
        onPlayingChange={handlePlayingChange}
        onCancelSilence={cancelSilence}
        nativeQueue={nativeQueue}
        onNativeQueueItem={syncNativeQueueItem}
        onNativeQueueComplete={completeNativeQueue}
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
        playbackRunMode={playbackRunMode}
        sequence={sequence}
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
