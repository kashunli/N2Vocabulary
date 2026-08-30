import { useCallback, type Dispatch, type SetStateAction } from "react";

import { useI18n } from "../../i18n";
import type { Entry } from "../../types";
import { markStatusOf, toggleMarkStatus } from "./markStatus";
import type { StudyStateStore } from "./studyStateTypes";

interface UseStudyActionsOptions {
  activeEntry?: Entry;
  setEntries: Dispatch<SetStateAction<Entry[]>>;
  setStatus: (status: string) => void;
  studyStore: StudyStateStore;
}

export function useStudyActions({
  activeEntry,
  setEntries,
  setStatus,
  studyStore,
}: UseStudyActionsOptions) {
  const {copy, localizeMessage} = useI18n();
  const toggleMark = useCallback(async (key: "known" | "flagged") => {
    if (!activeEntry) return;
    const currentStatus = markStatusOf(activeEntry.mark);
    const nextStatus = toggleMarkStatus(currentStatus, key);
    try {
      await studyStore.setMark(activeEntry.item_uuid, nextStatus);
      setEntries((current) => current.map((entry) => entry.entry_id === activeEntry.entry_id
        ? {...entry, mark: {...entry.mark, status: nextStatus}}
        : entry));
      setStatus(copy.markMessage(activeEntry.kanji, nextStatus));
    } catch (error: unknown) {
      setStatus(error instanceof Error ? localizeMessage(error.message) : copy.errors.updateStudyMark);
    }
  }, [activeEntry, copy, localizeMessage, setEntries, setStatus, studyStore]);

  return {
    toggleMark,
  };
}
