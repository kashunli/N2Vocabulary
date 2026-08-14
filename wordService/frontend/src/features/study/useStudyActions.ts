import { useCallback, type Dispatch, type SetStateAction } from "react";

import { exportUnitFlaggedAudio } from "../../api";
import type { Entry, UnitSummary } from "../../types";
import { markStatusOf, toggleMarkStatus } from "./markStatus";
import { unitLabel } from "./unitLabel";
import type { StudyStateStore } from "./studyStateTypes";

interface UseStudyActionsOptions {
  activeEntry?: Entry;
  allVisibleCovered: boolean;
  entries: Entry[];
  selectedBook: string;
  selectedUnit: number | null;
  setCoveredEntryIds: Dispatch<SetStateAction<Set<number>>>;
  setDetail: Dispatch<SetStateAction<Entry | undefined>>;
  setEntries: Dispatch<SetStateAction<Entry[]>>;
  setStatus: (status: string) => void;
  units: UnitSummary[];
  studyStore: StudyStateStore;
}

export function useStudyActions({
  activeEntry,
  allVisibleCovered,
  entries,
  selectedBook,
  selectedUnit,
  setCoveredEntryIds,
  setDetail,
  setEntries,
  setStatus,
    units,
    studyStore,
}: UseStudyActionsOptions) {
  const toggleMark = useCallback(async (key: "known" | "flagged") => {
    if (!activeEntry) return;
    const currentStatus = markStatusOf(activeEntry.mark);
    const nextStatus = toggleMarkStatus(currentStatus, key);
    try {
      await studyStore.setMark(activeEntry.item_uuid, nextStatus);
      setEntries((current) => current.map((entry) => entry.entry_id === activeEntry.entry_id
        ? {...entry, mark: {...entry.mark, status: nextStatus}}
        : entry));
      setDetail((current) => current && current.entry_id === activeEntry.entry_id
        ? {...current, mark: {...current.mark, status: nextStatus}}
        : current);
      setStatus(`${activeEntry.kanji} is ${nextStatus}.`);
    } catch (error: unknown) {
      setStatus(error instanceof Error ? error.message : "Could not update the study mark.");
    }
  }, [activeEntry, setDetail, setEntries, setStatus, studyStore]);

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

  return {
    exportFlaggedAudio,
    toggleCoverAll,
    toggleMark,
  };
}
