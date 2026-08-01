import { useEffect, type Dispatch, type SetStateAction } from "react";

import { getEntries } from "../../api";
import type { Entry } from "../../types";
import type { PlaybackMode } from "../player/playbackSettings";
import type { FilterState } from "./studyTypes";

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
}: UseStudyEntriesOptions) {
  useEffect(() => {
    let cancelled = false;
    setEntriesLoading(true);
    getEntries(selectedBook, selectedUnit ?? undefined, filterState, search)
      .then((payload) => {
        if (cancelled) return;
        setEntries(payload.items);
        resetPosition(payload.items);
      })
      .catch((error: unknown) => {
        if (!cancelled) setStatus(error instanceof Error ? error.message : "Could not load vocabulary.");
      })
      .finally(() => {
        if (!cancelled) setEntriesLoading(false);
      });
    return () => { cancelled = true; };
  }, [filterState, playbackMode, resetPosition, search, selectedBook, selectedUnit, setEntries, setEntriesLoading, setStatus]);
}
