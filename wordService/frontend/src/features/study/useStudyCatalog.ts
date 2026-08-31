import { useEffect, useMemo, useState } from "react";

import { getBooks, getEntries, getSummary, getUnits } from "../../api";
import { useI18n } from "../../i18n";
import { loadContentScope } from "./contentCache.mjs";
import { deriveCatalogPresentation } from "./catalogPresentation.mjs";
import type { BookSummary, Entry, UnitSummary, VocabularySummary } from "../../types";
import { markStatusOf } from "./markStatus";
import { isReviewDue, type StudySnapshot } from "./studyStateTypes";

interface UseStudyCatalogOptions {
  selectedBook: string;
  selectedUnit: number | null;
  studySnapshot: StudySnapshot;
}

interface LoadedScope {
  book: string;
  revision: string;
  selectedUnit: number | null;
  entries: Entry[];
}

export function useStudyCatalog({
  selectedBook,
  selectedUnit,
  studySnapshot,
}: UseStudyCatalogOptions) {
  const {copy, localizeMessage} = useI18n();
  const [books, setBooks] = useState<BookSummary[]>([]);
  const [catalogBook, setCatalogBook] = useState("");
  const [bookSummary, setBookSummary] = useState<VocabularySummary>();
  const [sourceUnits, setSourceUnits] = useState<UnitSummary[]>([]);
  const [loadedScope, setLoadedScope] = useState<LoadedScope>();
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [scopeLoading, setScopeLoading] = useState(false);
  const [status, setStatus] = useState("");

  useEffect(() => {
    getBooks()
      .then((payload) => setBooks(payload.items))
      .catch((error: unknown) => setStatus(error instanceof Error ? localizeMessage(error.message) : copy.errors.loadBooks));
  }, [copy.errors.loadBooks, localizeMessage, setStatus]);

  // Summary supplies the immutable content revision; unit metadata is small
  // and remains separate from the potentially large entry payloads.
  useEffect(() => {
    let cancelled = false;
    setCatalogLoading(true);
    Promise.all([getSummary(selectedBook), getUnits(selectedBook)])
      .then(([freshSummary, unitPayload]) => {
        if (cancelled) return;
        setCatalogBook(selectedBook);
        setBookSummary(freshSummary);
        setSourceUnits(unitPayload.items);
      })
      .catch((error: unknown) => {
        if (!cancelled) setStatus(error instanceof Error ? localizeMessage(error.message) : copy.errors.loadSections);
      })
      .finally(() => {
        if (!cancelled) setCatalogLoading(false);
      });
    return () => { cancelled = true; };
  }, [copy.errors.loadSections, localizeMessage, selectedBook, setStatus]);

  // A normal section selection requests only that unit. All sections is built
  // by combining cached units and fetching just the missing unit URLs.
  useEffect(() => {
    if (catalogBook !== selectedBook || !bookSummary || !sourceUnits.length) return undefined;
    let cancelled = false;
    const revision = bookSummary.content_revision;
    setScopeLoading(true);
    loadContentScope({
      book: selectedBook,
      revision,
      selectedUnit,
      units: sourceUnits,
      fetchUnit: (unit: number) => getEntries(selectedBook, revision, unit).then((payload) => payload.items),
    })
      .then((entries: Entry[]) => {
        if (!cancelled) setLoadedScope({book: selectedBook, revision, selectedUnit, entries});
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          // Mark this scope as settled so the previous section is not left on
          // screen after a failed request. The status message carries the
          // actual failure while the wall falls back to its empty state.
          setLoadedScope({book: selectedBook, revision, selectedUnit, entries: []});
          setStatus(error instanceof Error ? localizeMessage(error.message) : copy.errors.loadSections);
        }
      })
      .finally(() => {
        if (!cancelled) setScopeLoading(false);
      });
    return () => { cancelled = true; };
  }, [bookSummary, catalogBook, copy.errors.loadSections, localizeMessage, selectedBook, selectedUnit, setStatus, sourceUnits]);

  const allEntries = loadedScope
    && loadedScope.book === selectedBook
    && loadedScope.revision === bookSummary?.content_revision
    && loadedScope.selectedUnit === selectedUnit
    ? loadedScope.entries
    : [];
  const scopeReady = Boolean(
    loadedScope
    && loadedScope.book === selectedBook
    && loadedScope.revision === bookSummary?.content_revision
    && loadedScope.selectedUnit === selectedUnit,
  );

  const presentation = useMemo<{summary: VocabularySummary; units: UnitSummary[]} | undefined>(() => {
    if (!bookSummary || catalogBook !== selectedBook || !allEntries.length) return undefined;
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
  }, [allEntries, bookSummary, catalogBook, selectedBook, selectedUnit, sourceUnits, studySnapshot.cards]);

  return {
    books,
    contentLoading: catalogLoading || scopeLoading,
    setStatus,
    status,
    summary: presentation?.summary ?? bookSummary,
    units: presentation?.units ?? sourceUnits,
    allEntries,
    scopeReady,
  };
}
