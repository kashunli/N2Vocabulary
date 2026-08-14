import { useEffect, useState } from "react";

import { getBooks, getEntries, getEntry, getSummary, getUnits } from "../../api";
import type { BookSummary, Entry, UnitSummary, VocabularySummary } from "../../types";
import { isReviewDue, type StudySnapshot } from "./studyStateTypes";

interface UseStudyCatalogOptions {
  activeEntry?: Entry;
  selectedBook: string;
  selectedUnit: number | null;
  studySnapshot: StudySnapshot;
}

export function useStudyCatalog({
  activeEntry,
  selectedBook,
  selectedUnit,
  studySnapshot,
}: UseStudyCatalogOptions) {
  const [books, setBooks] = useState<BookSummary[]>([]);
  const [summary, setSummary] = useState<VocabularySummary>();
  const [units, setUnits] = useState<UnitSummary[]>([]);
  const [detail, setDetail] = useState<Entry>();
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
        const review = marks.filter(mark => isReviewDue(mark?.due_at)).length;
        setSummary({...nextSummary, known, flagged, review, unmarked: marks.filter(mark => !mark?.known && !mark?.flagged).length});
        setUnits(nextUnits.items.map(unit => {
          const unitEntries = allEntries.items.filter(entry => entry.unit.number === unit.number);
          return {
            ...unit,
            known: unitEntries.filter(entry => studySnapshot.cards[entry.item_uuid]?.known).length,
            flagged: unitEntries.filter(entry => studySnapshot.cards[entry.item_uuid]?.flagged).length,
            review: unitEntries.filter(entry => isReviewDue(studySnapshot.cards[entry.item_uuid]?.due_at)).length,
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

  return {
    books,
    detail,
    setDetail,
    setStatus,
    status,
    summary,
    units,
  };
}
