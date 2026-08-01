import { useCallback, useState } from "react";

import { exportUnitFlaggedAudio, updateExampleStar, updateMark } from "./api";
import { PlaybackSettingsModal } from "./features/player/PlaybackSettingsModal";
import { RailPlayer } from "./features/player/RailPlayer";
import { useStudyKeyboardShortcuts } from "./features/player/useStudyKeyboardShortcuts";
import { useStudyPlayback } from "./features/player/useStudyPlayback";
import { StarredView } from "./features/study/StarredView";
import { StudyHeader } from "./features/study/StudyHeader";
import { StudyWallView } from "./features/study/StudyWallView";
import { unitLabel } from "./features/study/unitLabel";
import { useStudyCatalog } from "./features/study/useStudyCatalog";
import { useStudyEntries } from "./features/study/useStudyEntries";
import type { FilterState } from "./features/study/studyTypes";
import type {
  Entry,
} from "./types";

export function App() {
  const [selectedBook, setSelectedBook] = useState("N2");
  const [selectedUnit, setSelectedUnit] = useState<number | null>(null);
  const [filterState, setFilterState] = useState<FilterState>("all");
  const [search, setSearch] = useState("");
  const [entries, setEntries] = useState<Entry[]>([]);
  const [entriesLoading, setEntriesLoading] = useState(false);
  const [coveredEntryIds, setCoveredEntryIds] = useState<Set<number>>(() => new Set());
  const [blurred, setBlurred] = useState(false);
  const [showStarred, setShowStarred] = useState(false);
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
  } = useStudyCatalog({activeEntry, selectedBook, selectedUnit, showStarred});
  const currentBook = books.find((book) => book.code === selectedBook);
  const selectedStarred = starredSentences.find((item) => (
    `${item.entry_id}:${item.position}` === selectedStarredKey
  ));
  const allVisibleCovered = entries.length > 0 && entries.every((entry) => coveredEntryIds.has(entry.entry_id));

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
  });

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

  useStudyKeyboardShortcuts({
    onBlurToggle: () => setBlurred((current) => !current),
    onMoveClip: moveClip,
    onReplay: replayFocused,
    onSetSettingsOpen: setSettingsOpen,
    onToggleMark: toggleMark,
    onTogglePlayback: togglePlayback,
    settingsOpen,
  });

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
        await refreshStarred();
      }
    } catch (error: unknown) {
      setStatus(error instanceof Error ? error.message : "Could not update the sentence star.");
    }
  }, [activeEntry, refreshStarred, selectedBook, showStarred]);

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
