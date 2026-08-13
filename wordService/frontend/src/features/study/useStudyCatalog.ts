import { useCallback, useEffect, useState } from "react";

import { getBooks, getEntries, getEntry, getStarredSentences, getSummary, getUnits } from "../../api";
import type { BookSummary, Entry, StarredSentence, UnitSummary, VocabularySummary } from "../../types";
import type { StudySnapshot } from "./studyStateTypes";

interface UseStudyCatalogOptions {
  activeEntry?: Entry;
  selectedBook: string;
  selectedUnit: number | null;
  showStarred: boolean;
  studySnapshot: StudySnapshot;
}

export function useStudyCatalog({
  activeEntry,
  selectedBook,
  selectedUnit,
  showStarred,
  studySnapshot,
}: UseStudyCatalogOptions) {
  const [books, setBooks] = useState<BookSummary[]>([]);
  const [summary, setSummary] = useState<VocabularySummary>();
  const [units, setUnits] = useState<UnitSummary[]>([]);
  const [detail, setDetail] = useState<Entry>();
  const [starredSentences, setStarredSentences] = useState<StarredSentence[]>([]);
  const [selectedStarredKey, setSelectedStarredKey] = useState<string>();
  const [status, setStatus] = useState("");

  useEffect(() => {
    getBooks()
      .then((payload) => setBooks(payload.items))
      .catch((error: unknown) => setStatus(error instanceof Error ? error.message : "Could not load books."));
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getSummary(selectedBook), getUnits(selectedBook), getEntries(selectedBook)])
      .then(([nextSummary, nextUnits, allEntries]) => {
        if (cancelled) return;
        const marks = allEntries.items.map(entry => studySnapshot.cards[entry.item_uuid]);
        const known = marks.filter(mark => mark?.known).length;
        const flagged = marks.filter(mark => mark?.flagged).length;
        setSummary({...nextSummary, known, flagged, unmarked: marks.filter(mark => !mark?.known && !mark?.flagged).length});
        setUnits(nextUnits.items.map(unit => {
          const unitEntries = allEntries.items.filter(entry => entry.unit.number === unit.number);
          return {
            ...unit,
            known: unitEntries.filter(entry => studySnapshot.cards[entry.item_uuid]?.known).length,
            flagged: unitEntries.filter(entry => studySnapshot.cards[entry.item_uuid]?.flagged).length,
            unmarked: unitEntries.filter(entry => {
              const mark = studySnapshot.cards[entry.item_uuid];
              return !mark?.known && !mark?.flagged;
            }).length,
          };
        }));
      })
      .catch((error: unknown) => {
        if (!cancelled) setStatus(error instanceof Error ? error.message : "Could not load sections.");
      });
    return () => { cancelled = true; };
  }, [selectedBook, studySnapshot]);

  useEffect(() => {
    if (!activeEntry) {
      setDetail(undefined);
      return undefined;
    }
    let cancelled = false;
    getEntry(activeEntry.entry_id, activeEntry.book_code)
      .then((nextDetail) => { if (!cancelled) setDetail(nextDetail); })
      .catch((error: unknown) => { if (!cancelled) setStatus(error instanceof Error ? error.message : "Could not load word details."); });
    return () => { cancelled = true; };
  }, [activeEntry, selectedBook]);

  useEffect(() => {
    if (!showStarred) return undefined;
    let cancelled = false;
    getStarredSentences(selectedBook, selectedUnit ?? undefined)
      .then((payload) => {
        if (cancelled) return;
        setStarredSentences(payload.items);
        setSelectedStarredKey((current) => payload.items.some((item) => `${item.entry_id}:${item.position}` === current)
          ? current
          : payload.items[0] ? `${payload.items[0].entry_id}:${payload.items[0].position}` : undefined);
      })
      .catch((error: unknown) => { if (!cancelled) setStatus(error instanceof Error ? error.message : "Could not load starred sentences."); });
    return () => { cancelled = true; };
  }, [selectedBook, selectedUnit, showStarred]);

  const refreshCatalog = useCallback(async () => {
    const [nextSummary, nextUnits] = await Promise.all([getSummary(selectedBook), getUnits(selectedBook)]);
    setSummary(nextSummary);
    setUnits(nextUnits.items);
  }, [selectedBook]);

  const refreshStarred = useCallback(async () => {
    const payload = await getStarredSentences(selectedBook, selectedUnit ?? undefined);
    setStarredSentences(payload.items);
    setSelectedStarredKey((current) => payload.items.some((item) => `${item.entry_id}:${item.position}` === current)
      ? current
      : payload.items[0] ? `${payload.items[0].entry_id}:${payload.items[0].position}` : undefined);
    return payload.items;
  }, [selectedBook, selectedUnit]);

  return {
    books,
    detail,
    refreshCatalog,
    refreshStarred,
    selectedStarredKey,
    setDetail,
    setSelectedStarredKey,
    setStarredSentences,
    setStatus,
    starredSentences,
    status,
    summary,
    units,
  };
}
