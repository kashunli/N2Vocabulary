import { useCallback, type Dispatch, type SetStateAction } from "react";

import { exportUnitFlaggedAudio, updateExampleStar } from "../../api";
import type { Entry, StarredSentence, UnitSummary } from "../../types";
import type { PlaybackPhase } from "../player/playbackSettings";
import { unitLabel } from "./unitLabel";
import type { StudyStateStore } from "./studyStateTypes";

interface UseStudyActionsOptions {
  activeEntry?: Entry;
  allVisibleCovered: boolean;
  entries: Entry[];
  refreshCatalog: () => Promise<void>;
  refreshStarred: () => Promise<StarredSentence[]>;
  selectedBook: string;
  selectedUnit: number | null;
  setCoveredEntryIds: Dispatch<SetStateAction<Set<number>>>;
  setDetail: Dispatch<SetStateAction<Entry | undefined>>;
  setEntries: Dispatch<SetStateAction<Entry[]>>;
  setShowStarred: Dispatch<SetStateAction<boolean>>;
  setStatus: (status: string) => void;
  selectEntry: (index: number, phase?: PlaybackPhase) => void;
  showStarred: boolean;
  units: UnitSummary[];
  studyStore: StudyStateStore;
}

export function useStudyActions({
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
  studyStore,
}: UseStudyActionsOptions) {
  const toggleMark = useCallback(async (key: "known" | "flagged") => {
    if (!activeEntry) return;
    const next = {
      known: !!activeEntry.mark?.known,
      flagged: !!activeEntry.mark?.flagged,
    };
    next[key] = !next[key];
    try {
      await studyStore.setMark(activeEntry.item_uuid, next);
      setEntries((current) => current.map((entry) => entry.entry_id === activeEntry.entry_id
        ? {...entry, mark: {...entry.mark, ...next}}
        : entry));
      setDetail((current) => current && current.entry_id === activeEntry.entry_id
        ? {...current, mark: {...current.mark, ...next}}
        : current);
      setStatus(`${activeEntry.kanji} is ${next[key] ? key : `not ${key}`}.`);
    } catch (error: unknown) {
      setStatus(error instanceof Error ? error.message : "Could not update the study mark.");
    }
  }, [activeEntry, setDetail, setEntries, setStatus, studyStore]);

  const toggleSentenceStar = useCallback(async () => {
    if (!activeEntry) return;
    const position = activeEntry.sentence_position ?? 0;
    try {
      const payload = await updateExampleStar(activeEntry.entry_id, position, !activeEntry.sentence_starred, activeEntry.book_code);
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
  }, [activeEntry, refreshStarred, setDetail, setEntries, setStatus, showStarred]);

  const toggleCoverAll = useCallback(() => {
    setCoveredEntryIds((current) => {
      const next = new Set(current);
      if (allVisibleCovered) entries.forEach((entry) => next.delete(entry.entry_id));
      else entries.forEach((entry) => next.add(entry.entry_id));
      return next;
    });
  }, [allVisibleCovered, entries, setCoveredEntryIds]);

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
  }, [selectedBook, selectedUnit, setStatus, units]);

  const focusStarredEntry = useCallback((entryId: number) => {
    const index = entries.findIndex((entry) => entry.entry_id === entryId);
    if (index >= 0) {
      setShowStarred(false);
      selectEntry(index, "sentence");
    } else {
      setStatus("The starred sentence is outside the current filtered list. Clear the search or filter to focus it.");
    }
  }, [entries, selectEntry, setShowStarred, setStatus]);

  return {
    exportFlaggedAudio,
    focusStarredEntry,
    toggleCoverAll,
    toggleMark,
    toggleSentenceStar,
  };
}
