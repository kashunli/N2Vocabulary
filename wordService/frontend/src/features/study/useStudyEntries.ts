import { useEffect, useRef, type Dispatch, type SetStateAction } from "react";

import { getEntries, resolveReviewEntries } from "../../api";
import type { Entry } from "../../types";
import type { PlaybackMode } from "../player/playbackSettings";
import type { FilterState } from "./studyTypes";
import type { StudyCardState, StudySnapshot } from "./studyStateTypes";

interface UseStudyEntriesOptions {
  filterState: FilterState;
  playbackMode: PlaybackMode;
  resetPosition: (entries: Entry[]) => void;
  reviewCards: StudyCardState[];
  reviewMode: boolean;
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
  reviewCards,
  reviewMode,
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
      reviewMode,
      reviewCards.map(card => [card.item_uuid, card.due_at, card.preferred_book_code, card.preferred_source_index]),
    ]);
    const preserveLoadedPlaylist = loadedQueryRef.current === queryKey;
    // Playing a card updates studySnapshot so its progress can be saved. Keep
    // the current rows mounted during that background refresh; replacing them
    // with the loading message empties the scroll pane and resets it to row 1.
    if (loadedQueryRef.current !== queryKey) setEntriesLoading(true);
    const loadEntries = reviewMode
      ? (async () => {
        const resolved: Entry[] = [];
        for (let offset = 0; offset < reviewCards.length; offset += 100) {
          const page = reviewCards.slice(offset, offset + 100);
          const payload = await resolveReviewEntries(page.map(card => ({
            item_uuid: card.item_uuid,
            preferred_book_code: card.preferred_book_code,
            preferred_source_index: card.preferred_source_index,
          })));
          const byUuid = new Map(payload.items.map(entry => [entry.item_uuid, entry]));
          for (const card of page) {
            const entry = byUuid.get(card.item_uuid);
            if (entry) {
              resolved.push({
                ...entry,
                mark: {...entry.mark, known: card.known, flagged: card.flagged},
              });
            }
          }
        }
        return {items: resolved};
      })()
      : getEntries(selectedBook, selectedUnit ?? undefined, "all", search);
    loadEntries.then((payload) => {
        if (cancelled) return;
        const loadedItems = payload.items
          .map(entry => {
            const card = studySnapshot.cards[entry.item_uuid];
            return {...entry, mark: {known: !!card?.known, flagged: !!card?.flagged, updated_at: card?.updated_at}};
          });
        const filteredItems = reviewMode ? loadedItems : loadedItems.filter(entry => filterState === "all"
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
  }, [filterState, playbackMode, resetPosition, reviewCards, reviewMode, search, selectedBook, selectedUnit, setEntries, setEntriesLoading, setStatus, studySnapshot]);
}
