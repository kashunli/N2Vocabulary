import { useCallback, useEffect, useState } from "react";

import { getBooks, getEntry, getStarredSentences, getSummary, getUnits } from "../../api";
import type { BookSummary, Entry, StarredSentence, UnitSummary, VocabularySummary } from "../../types";

interface UseStudyCatalogOptions {
  activeEntry?: Entry;
  selectedBook: string;
  selectedUnit: number | null;
  showStarred: boolean;
}

export function useStudyCatalog({
  activeEntry,
  selectedBook,
  selectedUnit,
  showStarred,
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
    Promise.all([getSummary(selectedBook), getUnits(selectedBook)])
      .then(([nextSummary, nextUnits]) => {
        if (cancelled) return;
        setSummary(nextSummary);
        setUnits(nextUnits.items);
      })
      .catch((error: unknown) => {
        if (!cancelled) setStatus(error instanceof Error ? error.message : "Could not load sections.");
      });
    return () => { cancelled = true; };
  }, [selectedBook]);

  useEffect(() => {
    if (!activeEntry) {
      setDetail(undefined);
      return undefined;
    }
    let cancelled = false;
    getEntry(activeEntry.entry_id, selectedBook)
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
