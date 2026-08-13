import { useEffect, useRef, useState } from "react";

import { PlaybackSettingsModal } from "./features/player/PlaybackSettingsModal";
import { RailPlayer } from "./features/player/RailPlayer";
import { useStudyKeyboardShortcuts } from "./features/player/useStudyKeyboardShortcuts";
import { useStudyPlayback } from "./features/player/useStudyPlayback";
import { StarredView } from "./features/study/StarredView";
import {AccountControls} from "./features/study/AccountControls";
import { StudyHeader } from "./features/study/StudyHeader";
import { StudyWallView } from "./features/study/StudyWallView";
import { useStudyActions } from "./features/study/useStudyActions";
import { useStudyCatalog } from "./features/study/useStudyCatalog";
import { useStudyEntries } from "./features/study/useStudyEntries";
import { readStudyFocus } from "./features/study/studyFocus";
import { readStudyViewState, saveStudyViewState } from "./features/study/studyViewState.mjs";
import { useStudyState } from "./features/study/useStudyState";
import type { ReviewSession } from "./features/study/studyStateTypes";
import type { FilterState } from "./features/study/studyTypes";
import type { Entry } from "./types";

function StudyApp({store, snapshot}: ReturnType<typeof useStudyState>) {
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
  const [reviewSession, setReviewSession] = useState<ReviewSession>();
  const reviewCompletionInFlight = useRef(new Set<string>());

  useEffect(() => {
    if (filterState !== "review") setReviewSession(undefined);
    reviewCompletionInFlight.current.clear();
  }, [filterState, search, selectedBook, selectedUnit]);

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
    entries,
    showStarred,
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
  });

  useStudyEntries({
    filterState,
    playbackMode,
    resetPosition,
    search,
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
        reviewSessionCount={filterState === "review" ? Object.keys(reviewSession?.expectedDueAtByItemUuid || {}).length : undefined}
        target={target}
        units={units}
        onOpenSettings={() => setSettingsOpen(true)}
        onSearch={setSearch}
        onSelectBook={(book) => { setSelectedBook(book); setSelectedUnit(null); setShowStarred(false); setReviewSession(undefined); }}
        onSelectFilter={(filter) => { setFilterState(filter); setShowStarred(false); if (filter !== "review") setReviewSession(undefined); }}
        onSelectUnit={(unit) => { setSelectedUnit(unit); setReviewSession(undefined); }}
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
        /> : <StudyWallView
          activeEntry={activeEntry}
          activeIndex={activeIndex}
          activePhase={activePhase}
          bookCode={activeEntry?.book_code || selectedBook}
          coveredEntryIds={coveredEntryIds}
          detail={detail}
          entries={entries}
          entriesLoading={entriesLoading}
          onSelectEntry={selectEntry}
          onSelectPhase={selectPhase}
          onToggleMark={toggleMark}
          onToggleSentenceStar={toggleSentenceStar}
          reviewSession={reviewSession}
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
        onPrevious={() => movePlaybackClip(-1)}
        onNext={() => movePlaybackClip(1)}
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

export function App() {
  const studyState = useStudyState();
  if (!studyState.ready) return <main className="react-shell"><p className="react-empty">Loading study state…</p></main>;
  return <><AccountControls state={studyState} /><StudyApp key={studyState.session?.user.id ?? "guest"} {...studyState} /></>;
}
