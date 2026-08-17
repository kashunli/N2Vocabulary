import { useEffect, useState } from "react";

import { getBooks, getEntries, getEntry, getSummary, getUnits } from "../../api";
import type { BookSummary, Entry, UnitSummary, VocabularySummary } from "../../types";
import { markStatusOf } from "./markStatus";
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
  const [allEntries, setAllEntries] = useState<Entry[]>([]);
  const [detail, setDetail] = useState<Entry>();
  const [status, setStatus] = useState("");

  useEffect(() => {
    getBooks()
      .then((payload) => setBooks(payload.items))
      .catch((error: unknown) => setStatus(error instanceof Error ? error.message : "Could not load books."));
  }, []);

  // Fetch the selected book's catalog once per book selection. The wall's
  // visible queue and the section dropdown counts are both derived from this
  // immutable list below, so playback/mark snapshot changes must not re-run
  // this network request.
  useEffect(() => {
    let cancelled = false;
    Promise.all([getSummary(selectedBook), getUnits(selectedBook), getEntries(selectedBook)])
      .then(([nextSummary, nextUnits, bookPayload]) => {
        if (cancelled) return;
        setAllEntries(bookPayload.items);
        setSummary(nextSummary);
        setUnits(nextUnits.items);
      })
      .catch((error: unknown) => {
        if (!cancelled) setStatus(error instanceof Error ? error.message : "Could not load sections.");
      });
    return () => { cancelled = true; };
  }, [selectedBook]);

  // Recompute the scoped header counts whenever marks/playback change the
  // snapshot. All inputs already live locally, so this never hits the network.
  useEffect(() => {
    if (!summary || !allEntries.length || allEntries[0].book_code !== selectedBook) return;
    // The wall's visible queue is section-scoped, so the filter counts must
    // use the same scope instead of always showing book-wide totals. Keep the
    // full book loaded because the section dropdown still needs per-unit
    // counts for every option.
    const scopedEntries = selectedUnit === null
      ? allEntries
      : allEntries.filter(entry => entry.unit.number === selectedUnit);
    const marks = scopedEntries.map(entry => studySnapshot.cards[entry.item_uuid]);
    const known = marks.filter(mark => markStatusOf(mark) === "known").length;
    const flagged = marks.filter(mark => markStatusOf(mark) === "flagged").length;
    const review = marks.filter(mark => isReviewDue(mark?.due_at)).length;
    setSummary({
      ...summary,
      entries: scopedEntries.length,
      units: selectedUnit === null ? summary.units : 1,
      known,
      flagged,
      review,
      unmarked: marks.filter(mark => markStatusOf(mark) === "unmarked").length,
    });
    setUnits(current => current.map(unit => {
      const unitEntries = allEntries.filter(entry => entry.unit.number === unit.number);
      return {
        ...unit,
        known: unitEntries.filter(entry => markStatusOf(studySnapshot.cards[entry.item_uuid]) === "known").length,
        flagged: unitEntries.filter(entry => markStatusOf(studySnapshot.cards[entry.item_uuid]) === "flagged").length,
        review: unitEntries.filter(entry => isReviewDue(studySnapshot.cards[entry.item_uuid]?.due_at)).length,
        unmarked: unitEntries.filter(entry => markStatusOf(studySnapshot.cards[entry.item_uuid]) === "unmarked").length,
      };
    }));
  }, [allEntries, selectedBook, selectedUnit, studySnapshot]);

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
