import { useEffect, useRef, type Dispatch, type SetStateAction } from "react";

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
  const loadedQueryRef = useRef<string | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    const queryKey = JSON.stringify([
      filterState,
      search,
      selectedBook,
      selectedUnit,
    ]);
    const preserveLoadedPlaylist = loadedQueryRef.current === queryKey;
    // Playing a card updates studySnapshot so its progress can be saved. Keep
    // the current rows mounted during that background refresh; replacing them
    // with the loading message empties the scroll pane and resets it to row 1.
    if (loadedQueryRef.current !== queryKey) setEntriesLoading(true);
    getEntries(selectedBook, selectedUnit ?? undefined, "all", search).then((payload) => {
        if (cancelled) return;
        const loadedItems = payload.items
          .map(entry => {
            const card = studySnapshot.cards[entry.item_uuid];
            return {...entry, mark: {known: !!card?.known, flagged: !!card?.flagged, due_at: card?.due_at, updated_at: card?.updated_at}};
          });
        const filteredItems = loadedItems.filter(entry => filterState === "all"
          || (filterState === "known" && entry.mark.known)
          || (filterState === "flagged" && entry.mark.flagged)
          || (filterState === "unmarked" && !entry.mark.known && !entry.mark.flagged));
        if (preserveLoadedPlaylist) {
          // A mark change should update the visible icon without changing the
          // learner's current queue. The next full reload reapplies the filter.
          const marksByItemUuid = new Map(loadedItems.map(entry => [entry.item_uuid, entry.mark]));
          setEntries(current => current.map(entry => {
            const mark = marksByItemUuid.get(entry.item_uuid);
            return mark ? {...entry, mark} : entry;
          }));
        } else {
          setEntries(filteredItems);
          resetPosition(filteredItems);
        }
        loadedQueryRef.current = queryKey;
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
