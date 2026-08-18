import { useEffect, useRef, type Dispatch, type SetStateAction } from "react";

import type { Entry } from "../../types";
import { markStatusOf } from "./markStatus";
import type { FilterState } from "./studyTypes";
import { isReviewDue, type ReviewSession, type StudySnapshot } from "./studyStateTypes";

interface UseStudyEntriesOptions {
  allEntries: Entry[];
  filterState: FilterState;
  resetPosition: (entries: Entry[]) => void;
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
  allEntries,
  filterState,
  resetPosition,
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
  // The snapshot changes on every playback/mark action. The derive effect must
  // not re-run for those changes (the list itself is immutable for a scope),
  // but it still needs the latest snapshot when it runs, so read it through a
  // ref instead of a dependency.
  const studySnapshotRef = useRef(studySnapshot);
  studySnapshotRef.current = studySnapshot;
  const reviewSessionRef = useRef(reviewSession);
  reviewSessionRef.current = reviewSession;
  const resetPositionRef = useRef(resetPosition);
  resetPositionRef.current = resetPosition;

  // The visible queue is a client-side derivation of the book's cached entries.
  // Content is immutable for a scope, so unit/filter switches never hit the
  // network; only a book switch reloads allEntries upstream.
  useEffect(() => {
    if (!allEntries.length || allEntries[0].book_code !== selectedBook) return;
    const scopeKey = JSON.stringify([selectedBook, selectedUnit]);
    const queryKey = JSON.stringify([filterState, scopeKey]);
    const preserveLoadedPlaylist = loadedQueryRef.current === queryKey;
    // Playing a card updates studySnapshot so its progress can be saved. Keep
    // the current rows mounted during that background refresh; replacing them
    // with the loading message empties the scroll pane and resets it to row 1.
    if (loadedQueryRef.current !== queryKey) setEntriesLoading(true);
    const scopedItems = selectedUnit === null
      ? allEntries
      : allEntries.filter(entry => entry.unit.number === selectedUnit);
    const loadedItems = scopedItems.map(entry => {
      const card = studySnapshotRef.current.cards[entry.item_uuid];
      return {...entry, mark: {status: markStatusOf(card), due_at: card?.due_at, review_level: card?.review_level, last_reviewed_at: card?.last_reviewed_at, updated_at: card?.updated_at}};
    });
    const reviewNow = Date.now();
    const session = filterState === "review" && reviewSessionRef.current?.scopeKey === scopeKey
      ? reviewSessionRef.current
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
      resetPositionRef.current(filteredItems);
    }
    loadedQueryRef.current = queryKey;
    setEntriesLoading(false);
  }, [allEntries, filterState, selectedBook, selectedUnit, setEntries, setEntriesLoading, setReviewSession, setStatus]);

  // Refresh visible marks from the snapshot without recomputing the queue. The
  // scope derivation above runs once per (book, unit, filter) selection; each
  // play or mark action only needs the status merged into the mounted rows.
  useEffect(() => {
    setEntries(current => current.map(entry => {
      const card = studySnapshot.cards[entry.item_uuid];
      return {...entry, mark: {status: markStatusOf(card), due_at: card?.due_at, review_level: card?.review_level, last_reviewed_at: card?.last_reviewed_at, updated_at: card?.updated_at}};
    }));
  }, [setEntries, studySnapshot]);
}
