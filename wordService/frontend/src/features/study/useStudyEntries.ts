import { useEffect, type Dispatch, type SetStateAction } from "react";

import { getEntries } from "../../api";
import type { Entry } from "../../types";
import type { PlaybackMode } from "../player/playbackSettings";
import type { FilterState } from "./studyTypes";
import type { StudySnapshot } from "./studyStateTypes";

interface UseStudyEntriesOptions {
  filterState: FilterState;
  playbackMode: PlaybackMode;
  resetPosition: (entries: Entry[]) => void;
  search: string;
  selectedBook: string;
  selectedUnit: number | null;
  setEntries: Dispatch<SetStateAction<Entry[]>>;
  setEntriesLoading: Dispatch<SetStateAction<boolean>>;
  setStatus: (status: string) => void;
  studySnapshot: StudySnapshot;
}

export function useStudyEntries({
  filterState,
  playbackMode,
  resetPosition,
  search,
  selectedBook,
  selectedUnit,
  setEntries,
  setEntriesLoading,
  setStatus,
  studySnapshot,
}: UseStudyEntriesOptions) {
  useEffect(() => {
    let cancelled = false;
    setEntriesLoading(true);
    getEntries(selectedBook, selectedUnit ?? undefined, "all", search)
      .then((payload) => {
        if (cancelled) return;
        const items = payload.items
          .map(entry => {
            const card = studySnapshot.cards[entry.item_uuid];
            return {...entry, mark: {known: !!card?.known, flagged: !!card?.flagged, updated_at: card?.updated_at}};
          })
          .filter(entry => filterState === "all"
            || (filterState === "known" && entry.mark.known)
            || (filterState === "flagged" && entry.mark.flagged)
            || (filterState === "unmarked" && !entry.mark.known && !entry.mark.flagged));
        setEntries(items);
        resetPosition(items);
      })
      .catch((error: unknown) => {
        if (!cancelled) setStatus(error instanceof Error ? error.message : "Could not load vocabulary.");
      })
      .finally(() => {
        if (!cancelled) setEntriesLoading(false);
      });
    return () => { cancelled = true; };
  }, [filterState, playbackMode, resetPosition, search, selectedBook, selectedUnit, setEntries, setEntriesLoading, setStatus, studySnapshot]);
}
