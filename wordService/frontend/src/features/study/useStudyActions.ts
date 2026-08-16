import { useCallback, type Dispatch, type SetStateAction } from "react";

import type { Entry } from "../../types";
import { markStatusOf, toggleMarkStatus } from "./markStatus";
import type { StudyStateStore } from "./studyStateTypes";

interface UseStudyActionsOptions {
  activeEntry?: Entry;
  setDetail: Dispatch<SetStateAction<Entry | undefined>>;
  setEntries: Dispatch<SetStateAction<Entry[]>>;
  setStatus: (status: string) => void;
  studyStore: StudyStateStore;
}

export function useStudyActions({
  activeEntry,
  setDetail,
  setEntries,
  setStatus,
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

  return {
    toggleMark,
  };
}
