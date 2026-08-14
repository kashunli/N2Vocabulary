import { useEffect, useRef, type Dispatch, type SetStateAction } from "react";

import { getEntries } from "../../api";
import type { Entry } from "../../types";
import type { PlaybackMode } from "../player/playbackSettings";
import { markStatusOf } from "./markStatus";
import type { FilterState } from "./studyTypes";
import { isReviewDue, type ReviewSession, type StudySnapshot } from "./studyStateTypes";

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
  reviewSession?: ReviewSession;
  setReviewSession: Dispatch<SetStateAction<ReviewSession | undefined>>;
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
  reviewSession,
  setReviewSession,
  studySnapshot,
}: UseStudyEntriesOptions) {
  const loadedQueryRef = useRef<string | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    const scopeKey = JSON.stringify([search, selectedBook, selectedUnit]);
    const queryKey = JSON.stringify([filterState, scopeKey]);
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
            return {...entry, mark: {status: markStatusOf(card), due_at: card?.due_at, review_level: card?.review_level, last_reviewed_at: card?.last_reviewed_at, updated_at: card?.updated_at}};
          });
        const reviewNow = Date.now();
        const session = filterState === "review" && reviewSession?.scopeKey === scopeKey
          ? reviewSession
          : undefined;
        const dueItems = loadedItems.filter(entry => isReviewDue(entry.mark.due_at, reviewNow));
        if (filterState === "review" && !session) {
          const expectedDueAtByItemUuid = Object.fromEntries(dueItems.flatMap(entry => entry.mark.due_at ? [[entry.item_uuid, entry.mark.due_at]] : []));
          setReviewSession({scopeKey, expectedDueAtByItemUuid, completedByItemUuid: {}});
        }
        const filteredItems = loadedItems.filter(entry => filterState === "all"
          || (filterState === "review" && (session
            ? Object.hasOwn(session.expectedDueAtByItemUuid, entry.item_uuid)
            : isReviewDue(entry.mark.due_at, reviewNow)))
          || (filterState === "known" && markStatusOf(entry.mark) === "known")
          || (filterState === "flagged" && markStatusOf(entry.mark) === "flagged")
          || (filterState === "unmarked" && markStatusOf(entry.mark) === "unmarked"));
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
  }, [filterState, playbackMode, resetPosition, reviewSession, search, selectedBook, selectedUnit, setEntries, setEntriesLoading, setReviewSession, setStatus, studySnapshot]);
}
