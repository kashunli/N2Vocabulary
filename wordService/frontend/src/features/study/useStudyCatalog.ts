import { useEffect, useState } from "react";

import { getBooks, getEntries, getSummary, getUnits } from "../../api";
import { readContentBook, writeContentBook } from "./contentCache.mjs";
import type { BookSummary, Entry, UnitSummary, VocabularySummary } from "../../types";
import { markStatusOf } from "./markStatus";
import { isReviewDue, type StudySnapshot } from "./studyStateTypes";

interface UseStudyCatalogOptions {
  selectedBook: string;
  selectedUnit: number | null;
  studySnapshot: StudySnapshot;
}

export function useStudyCatalog({
  selectedBook,
  selectedUnit,
  studySnapshot,
}: UseStudyCatalogOptions) {
  const [books, setBooks] = useState<BookSummary[]>([]);
  const [summary, setSummary] = useState<VocabularySummary>();
  const [units, setUnits] = useState<UnitSummary[]>([]);
  const [allEntries, setAllEntries] = useState<Entry[]>([]);
  const [contentLoading, setContentLoading] = useState(false);
  const [status, setStatus] = useState("");

  useEffect(() => {
    getBooks()
      .then((payload) => setBooks(payload.items))
      .catch((error: unknown) => setStatus(error instanceof Error ? error.message : "Could not load books."));
  }, [setStatus]);

  // Load the selected book's content once and keep it local. Book content is
  // immutable, so a fresh summary only validates the cached revision; units and
  // entries are refetched only when the server fingerprint changed. There is no
  // per-entry detail request: every card field ships in the list payload.
  useEffect(() => {
    let cancelled = false;
    setContentLoading(true);
    getSummary(selectedBook)
      .then(async (freshSummary) => {
        const cached = readContentBook(selectedBook);
        if (cached && cached.revision === freshSummary.content_revision) {
          if (cancelled) return;
          setSummary(freshSummary);
          setUnits(cached.units);
          setAllEntries(cached.allEntries);
          return;
        }
        const [nextUnits, bookPayload] = await Promise.all([
          getUnits(selectedBook),
          getEntries(selectedBook),
        ]);
        if (cancelled) return;
        writeContentBook(selectedBook, {
          revision: freshSummary.content_revision,
          summary: freshSummary,
          units: nextUnits.items,
          allEntries: bookPayload.items,
        });
        setSummary(freshSummary);
        setUnits(nextUnits.items);
        setAllEntries(bookPayload.items);
      })
      .catch((error: unknown) => {
        if (!cancelled) setStatus(error instanceof Error ? error.message : "Could not load sections.");
      })
      .finally(() => {
        if (!cancelled) setContentLoading(false);
      });
    return () => { cancelled = true; };
  }, [selectedBook, setStatus]);

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

  return {
    books,
    contentLoading,
    setStatus,
    status,
    summary,
    units,
    allEntries,
  };
}
