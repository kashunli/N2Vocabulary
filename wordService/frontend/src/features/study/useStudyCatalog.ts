import { useEffect, useMemo, useState } from "react";

import { getBooks, getEntries, getSummary, getUnits } from "../../api";
import { useI18n } from "../../i18n";
import { readContentBook, writeContentBook } from "./contentCache.mjs";
import { deriveCatalogPresentation } from "./catalogPresentation.mjs";
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
  const {copy, localizeMessage} = useI18n();
  const [books, setBooks] = useState<BookSummary[]>([]);
  const [bookSummary, setBookSummary] = useState<VocabularySummary>();
  const [sourceUnits, setSourceUnits] = useState<UnitSummary[]>([]);
  const [allEntries, setAllEntries] = useState<Entry[]>([]);
  const [contentLoading, setContentLoading] = useState(false);
  const [status, setStatus] = useState("");

  useEffect(() => {
    getBooks()
      .then((payload) => setBooks(payload.items))
      .catch((error: unknown) => setStatus(error instanceof Error ? localizeMessage(error.message) : copy.errors.loadBooks));
  }, [copy.errors.loadBooks, localizeMessage, setStatus]);

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
          setBookSummary(freshSummary);
          setSourceUnits(cached.units);
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
        setBookSummary(freshSummary);
        setSourceUnits(nextUnits.items);
        setAllEntries(bookPayload.items);
      })
      .catch((error: unknown) => {
        if (!cancelled) setStatus(error instanceof Error ? localizeMessage(error.message) : copy.errors.loadSections);
      })
      .finally(() => {
        if (!cancelled) setContentLoading(false);
      });
    return () => { cancelled = true; };
  }, [copy.errors.loadSections, localizeMessage, selectedBook, setStatus]);

  const presentation = useMemo<{summary: VocabularySummary; units: UnitSummary[]} | undefined>(() => {
    if (!bookSummary || !allEntries.length || allEntries[0].book_code !== selectedBook) {
      return undefined;
    }
    return deriveCatalogPresentation({
      bookSummary,
      sourceUnits,
      allEntries,
      selectedBook,
      selectedUnit,
      cards: studySnapshot.cards,
      markStatusOf,
      isReviewDue,
    });
  }, [allEntries, bookSummary, selectedBook, selectedUnit, sourceUnits, studySnapshot.cards]);

  return {
    books,
    contentLoading,
    setStatus,
    status,
    summary: presentation?.summary ?? bookSummary,
    units: presentation?.units ?? sourceUnits,
    allEntries,
  };
}
