import { useEffect, useState } from "react";

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
import type { FilterState } from "./features/study/studyTypes";
import type {
  Entry,
} from "./types";

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
    playbackRunMode,
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
    togglePlaybackRunMode,
    togglePlayback,
  } = useStudyPlayback({entries, showStarred, onCompleteCard: entry => { void store.recordPlayed(entry).catch(error => setStatus(error instanceof Error ? error.message : "Could not save playback.")); }});
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
        /> : <StudyWallView
          activeEntry={activeEntry}
          activeIndex={activeIndex}
          activePhase={activePhase}
          bookCode={selectedBook}
          coveredEntryIds={coveredEntryIds}
          detail={detail}
          entries={entries}
          entriesLoading={entriesLoading}
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
  return <><AccountControls state={studyState} />{window.location.pathname.replace(/\/$/, "") === "/review"
    ? <ReviewApp key={studyState.session?.user.id ?? "guest"} store={studyState.store} accountEmail={studyState.session?.user.email} />
    : <StudyApp {...studyState} />}</>;
}
