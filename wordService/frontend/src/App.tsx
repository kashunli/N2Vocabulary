import { useCallback, useEffect, useState } from "react";

import { PlaybackSettingsModal } from "./features/player/PlaybackSettingsModal";
import { RailPlayer } from "./features/player/RailPlayer";
import { useStudyKeyboardShortcuts } from "./features/player/useStudyKeyboardShortcuts";
import { useStudyPlayback } from "./features/player/useStudyPlayback";
import { StarredView } from "./features/study/StarredView";
import { ReviewApp } from "./features/study/ReviewApp";
import {AccountControls} from "./features/study/AccountControls";
import { StudyHeader } from "./features/study/StudyHeader";
import { StudyWallView } from "./features/study/StudyWallView";
import { useStudyActions } from "./features/study/useStudyActions";
import { useStudyCatalog } from "./features/study/useStudyCatalog";
import { useStudyEntries } from "./features/study/useStudyEntries";
import { readStudyFocus } from "./features/study/studyFocus";
import { readStudyViewState, saveStudyViewState } from "./features/study/studyViewState.mjs";
import { useStudyState } from "./features/study/useStudyState";
import { nextGoodIntervalDays } from "./features/study/reviewScheduler.mjs";
import type { FilterState } from "./features/study/studyTypes";
import type {
  Entry,
} from "./types";
import type { ReviewGrade, StudyCardState } from "./features/study/studyStateTypes";

function StudyApp({store, snapshot, dueCount}: ReturnType<typeof useStudyState>) {
  const [initialView] = useState(() => readStudyViewState());
  const [selectedBook, setSelectedBook] = useState(() => initialView.selectedBook || readStudyFocus()?.bookCode || "N2");
  const [selectedUnit, setSelectedUnit] = useState<number | null>(() => initialView.selectedUnit ?? null);
  const [filterState, setFilterState] = useState<FilterState>(() => initialView.filterState || "all");
  const [search, setSearch] = useState(() => initialView.search || "");
  const [entries, setEntries] = useState<Entry[]>([]);
  const [entriesLoading, setEntriesLoading] = useState(false);
  const [coveredEntryIds, setCoveredEntryIds] = useState<Set<number>>(() => new Set());
  const [blurred, setBlurred] = useState(false);
  const [showStarred, setShowStarred] = useState(() => initialView.view === "starred");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [reviewMode, setReviewMode] = useState(false);
  const [reviewCards, setReviewCards] = useState<StudyCardState[]>([]);
  const [reviewPosition, setReviewPosition] = useState(0);
  const [pendingReviewGrade, setPendingReviewGrade] = useState<ReviewGrade>("again");
  const [reviewCompleted, setReviewCompleted] = useState<Set<string>>(() => new Set());
  const [reviewAutoplay, setReviewAutoplay] = useState(false);
  const reviewCurrent = reviewMode ? entries[reviewPosition] : undefined;
  const playbackEntries = reviewMode ? (reviewCurrent ? [reviewCurrent] : []) : entries;

  const commitReviewAndAdvance = useCallback(async () => {
    if (!reviewMode || !reviewCurrent) return;
    const itemUuid = reviewCurrent.item_uuid;
    try {
      const updatedCard = await store.grade(itemUuid, pendingReviewGrade);
      setEntries((current) => current.map((entry) => entry.item_uuid === itemUuid
        ? {...entry, mark: {...entry.mark, known: updatedCard.known, flagged: updatedCard.flagged}}
        : entry));
      setReviewCompleted((current) => new Set(current).add(itemUuid));
      const nextPosition = reviewPosition + 1;
      setReviewPosition(nextPosition);
      setPendingReviewGrade("again");
      // Moving forward in review is an explicit navigation action, so the
      // newly focused card should play in both Single and Consecutive modes.
      setReviewAutoplay(nextPosition < entries.length);
      setStatus("");
    } catch (error: unknown) {
      setStatus(error instanceof Error ? error.message : "Could not save the review grade.");
    }
  }, [entries.length, pendingReviewGrade, reviewCurrent, reviewMode, reviewPosition, store]);

  const {
    activeEntry: playbackEntry,
    activeIndex: playbackIndex,
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
    moveClip: movePlaybackClip,
    pauseRequest,
    playbackActive,
    playbackMode,
    postSentenceSilence,
    postWordSilence,
    playbackRunMode,
    playRequest,
    replayFocused,
    replayRequest,
    resetPlaybackSettings,
    resetPosition,
    selectEntry: selectPlaybackEntry,
    selectPhase,
    stopPlayback,
    stopRequest,
    target,
    togglePlaybackRunMode,
    togglePlayback,
  } = useStudyPlayback({
    entries: playbackEntries,
    showStarred,
    stopAfterEntry: reviewMode,
    onCompleteCard: entry => { void store.recordPlayed(entry).catch(error => setStatus(error instanceof Error ? error.message : "Could not save playback.")); },
    onConsecutiveSequenceComplete: reviewMode ? () => { void commitReviewAndAdvance(); } : undefined,
  });
  const activeEntry = reviewMode ? reviewCurrent : playbackEntry;
  const activeIndex = reviewMode ? reviewPosition : playbackIndex;
  const reviewCurrentCard = reviewCurrent ? snapshot.cards[reviewCurrent.item_uuid] || reviewCards[reviewPosition] : undefined;

  const playCurrentReviewEntry = useCallback(() => {
    if (!reviewCurrent) return;
    const phase = playbackMode === "sentences" && reviewCurrent.sentence_audio_url ? "sentence" : "word";
    selectPhase(phase);
  }, [playbackMode, reviewCurrent, selectPhase]);

  const selectReviewEntry = useCallback((index: number) => {
    if (!reviewMode || index < 0 || index >= entries.length) return;
    stopPlayback();
    setReviewPosition(index);
    setPendingReviewGrade("again");
    setReviewAutoplay(true);
    setStatus("");
  }, [entries.length, reviewMode, stopPlayback]);

  const nextReview = useCallback(() => {
    if (!reviewCurrent) return;
    if (playbackMode === "both" && activePhase === "word" && reviewCurrent.sentence_audio_url) {
      selectPhase("sentence");
      return;
    }
    void commitReviewAndAdvance();
  }, [activePhase, commitReviewAndAdvance, playbackMode, reviewCurrent, selectPhase]);

  const previousReview = useCallback(() => {
    if (!reviewCurrent) return;
    if (playbackMode === "both" && activePhase === "sentence") {
      movePlaybackClip(-1);
      return;
    }
    if (reviewPosition > 0) {
      stopPlayback();
      setReviewPosition(reviewPosition - 1);
      setPendingReviewGrade("again");
      setReviewAutoplay(true);
    }
  }, [activePhase, movePlaybackClip, playbackMode, reviewCurrent, reviewPosition, stopPlayback]);

  useEffect(() => {
    if (!reviewMode || !reviewCurrent || !reviewAutoplay) return;
    setReviewAutoplay(false);
    playCurrentReviewEntry();
  }, [playCurrentReviewEntry, reviewAutoplay, reviewCurrent?.item_uuid, reviewMode]);

  const moveClip = useCallback((direction: -1 | 1) => {
    if (reviewMode) {
      if (direction > 0) nextReview();
      else previousReview();
      return;
    }
    movePlaybackClip(direction);
  }, [movePlaybackClip, nextReview, previousReview, reviewMode]);

  const selectEntry = reviewMode ? selectReviewEntry : selectPlaybackEntry;
  const {
    books,
    detail,
    refreshCatalog,
    refreshStarred,
    selectedStarredKey,
    setDetail,
    setSelectedStarredKey,
    setStatus,
    starredSentences,
    status,
    summary,
    units,
  } = useStudyCatalog({activeEntry, selectedBook, selectedUnit, showStarred, studySnapshot: snapshot});

  const resetEntriesPosition = useCallback((nextEntries: Entry[]) => {
    if (!reviewMode) resetPosition(nextEntries);
  }, [resetPosition, reviewMode]);

  const openReview = useCallback(() => {
    const cards = store.dueCards();
    if (!cards.length) return;
    stopPlayback();
    setEntries([]);
    setReviewCards(cards);
    setReviewPosition(0);
    setReviewCompleted(new Set());
    setPendingReviewGrade("again");
    // The first due card follows the same autoplay contract as a normal
    // study-wall selection once the review list has finished loading.
    setReviewAutoplay(true);
    setCoveredEntryIds(new Set());
    setShowStarred(false);
    setReviewMode(true);
    setStatus("");
  }, [setStatus, stopPlayback, store]);

  const closeReview = useCallback(() => {
    stopPlayback();
    setReviewMode(false);
    setReviewCards([]);
    setReviewPosition(0);
    setReviewCompleted(new Set());
    setPendingReviewGrade("again");
    setReviewAutoplay(false);
    setEntries([]);
    setStatus("");
  }, [setStatus, stopPlayback]);

  useEffect(() => {
    if (!reviewMode) return undefined;
    const onKeyDown = (event: KeyboardEvent) => {
      const targetElement = event.target;
      if (targetElement instanceof HTMLElement && targetElement.closest("input, select, textarea, [contenteditable='true']")) return;
      const grade = event.key === "1" ? "again" : event.key === "2" ? "hard" : event.key === "3" ? "good" : undefined;
      if (!grade) return;
      event.preventDefault();
      setPendingReviewGrade(grade);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [reviewMode]);
  useEffect(() => {
    saveStudyViewState({
      selectedBook,
      selectedUnit,
      filterState,
      search,
      view: showStarred ? "starred" : "cards",
    });
  }, [filterState, search, selectedBook, selectedUnit, showStarred]);

  useEffect(() => {
    if (selectedUnit !== null && units.length && !units.some((unit) => unit.number === selectedUnit)) {
      setSelectedUnit(null);
    }
  }, [selectedUnit, units]);
  const currentBook = books.find((book) => book.code === selectedBook);
  const selectedStarred = starredSentences.find((item) => (
    `${item.entry_id}:${item.position}` === selectedStarredKey
  ));
  const allVisibleCovered = entries.length > 0 && entries.every((entry) => coveredEntryIds.has(entry.entry_id));

  const {
    exportFlaggedAudio,
    focusStarredEntry,
    toggleCoverAll,
    toggleMark,
    toggleSentenceStar,
  } = useStudyActions({
    activeEntry,
    allVisibleCovered,
    entries,
    refreshCatalog,
    refreshStarred,
    reviewMode,
    selectedBook,
    selectedUnit,
    setCoveredEntryIds,
    setDetail,
    setEntries,
    setShowStarred,
    setStatus,
    selectEntry,
    showStarred,
    units,
    studyStore: store,
    onSelectReviewGrade: setPendingReviewGrade,
  });

  useStudyEntries({
    filterState,
    playbackMode,
    resetPosition: resetEntriesPosition,
    reviewCards,
    reviewMode,
    search,
    selectedBook,
    selectedUnit,
    setEntries,
    setEntriesLoading,
    setStatus,
    studySnapshot: snapshot,
  });

  useStudyKeyboardShortcuts({
    onBlurToggle: () => setBlurred((current) => !current),
    onMoveClip: moveClip,
    onReplay: replayFocused,
    onSetSettingsOpen: setSettingsOpen,
    onToggleMark: toggleMark,
    onTogglePlayback: togglePlayback,
    settingsOpen,
  });

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
        playbackRunMode={playbackRunMode}
        search={search}
        selectedBook={selectedBook}
        selectedUnit={selectedUnit}
        showStarred={showStarred}
        summary={summary}
        target={target}
        units={units}
        dueCount={dueCount}
        reviewMode={reviewMode}
        onOpenSettings={() => setSettingsOpen(true)}
        onToggleReview={reviewMode ? closeReview : openReview}
        onSearch={(value) => { if (reviewMode) closeReview(); setSearch(value); }}
        onSelectBook={(book) => { if (reviewMode) closeReview(); setSelectedBook(book); setSelectedUnit(null); setShowStarred(false); }}
        onSelectFilter={(filter) => { if (reviewMode) closeReview(); setFilterState(filter); setShowStarred(false); }}
        onSelectUnit={(unit) => { if (reviewMode) closeReview(); setSelectedUnit(unit); }}
        onToggleBlur={() => setBlurred((current) => !current)}
        onToggleCoverAll={toggleCoverAll}
        onTogglePlayback={togglePlayback}
        onToggleStarred={() => { if (reviewMode) closeReview(); else setShowStarred((current) => !current); }}
      />
      {status ? <div className="react-status" role="status" aria-live="polite">{status}</div> : null}

      {reviewMode ? <section className="review-grade-bar" aria-label="Pending review grade">
        <span>Review due · {reviewCompleted.size}/{reviewCards.length} completed</span>
        {reviewCurrent ? <>
          <button type="button" className={pendingReviewGrade === "again" ? "is-selected" : ""} onClick={() => setPendingReviewGrade("again")}>1 · Again · 10m</button>
          <button type="button" className={pendingReviewGrade === "hard" ? "is-selected" : ""} onClick={() => setPendingReviewGrade("hard")}>2 · ⚑ Hard · 1d</button>
          <button type="button" className={pendingReviewGrade === "good" ? "is-selected" : ""} onClick={() => setPendingReviewGrade("good")}>3 · ✓ Good · {nextGoodIntervalDays(reviewCurrentCard?.good_step ?? 0)}d</button>
        </> : null}
      </section> : null}

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
        /> : <StudyWallView
          activeEntry={activeEntry}
          activeIndex={activeIndex}
          activePhase={activePhase}
          bookCode={activeEntry?.book_code || selectedBook}
          coveredEntryIds={coveredEntryIds}
          detail={detail}
          entries={entries}
          entriesLoading={entriesLoading}
          emptyMessage={reviewMode
            ? entries.length ? "Review complete. Choose Back to study list to continue." : "Loading review list…"
            : undefined}
          onSelectEntry={selectEntry}
          onSelectPhase={selectPhase}
          onToggleMark={toggleMark}
          onToggleSentenceStar={toggleSentenceStar}
        />}
      </div>

      <RailPlayer
        target={target}
        autoPlay={autoAdvance}
        isPlaybackActive={playbackActive}
        isSilencePlaying={isSilencePlaying}
        playbackRunMode={playbackRunMode}
        onPlayingChange={handlePlayingChange}
        playRequest={playRequest}
        replayRequest={replayRequest}
        pauseRequest={pauseRequest}
        stopRequest={stopRequest}
        onEnded={handlePlaybackEnd}
        onTogglePlayback={togglePlayback}
        onTogglePlaybackRunMode={togglePlaybackRunMode}
        onReplay={replayFocused}
        onPrevious={() => moveClip(-1)}
        onNext={() => moveClip(1)}
        onStop={stopPlayback}
        canPrevious={reviewMode ? !!reviewCurrent && (reviewPosition > 0 || (playbackMode === "both" && activePhase === "sentence")) : canPrevious}
        canNext={reviewMode ? !!reviewCurrent : canNext}
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

export function App() {
  const studyState = useStudyState();
  if (!studyState.ready) return <main className="react-shell"><p className="react-empty">Loading study state…</p></main>;
  return <><AccountControls state={studyState} />{window.location.pathname.replace(/\/$/, "") === "/review"
    ? <ReviewApp key={studyState.session?.user.id ?? "guest"} store={studyState.store} accountEmail={studyState.session?.user.email} />
    : <StudyApp key={studyState.session?.user.id ?? "guest"} {...studyState} />}</>;
}
