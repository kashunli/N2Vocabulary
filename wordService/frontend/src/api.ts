import type {
  BookSummary,
  Entry,
  Mark,
  StarredSentence,
  UnitSummary,
  VocabularySummary,
} from "./types";

async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) throw new Error(await response.text() || `Request failed: ${response.status}`);
  return response.json() as Promise<T>;
}

export function getUnits(book = "N2") {
  return getJson<{ items: UnitSummary[] }>(`/api/units?book=${encodeURIComponent(book)}`);
}

export function getBooks() {
  return getJson<{ items: BookSummary[] }>("/api/books");
}

export function getSummary(book = "N2") {
  return getJson<VocabularySummary>(`/api/summary?book=${encodeURIComponent(book)}`);
}

export function getEntries(
  book = "N2",
  unit?: number,
  state: "all" | "unmarked" | "known" | "flagged" = "all",
  search = "",
) {
  const params = new URLSearchParams({ book });
  if (unit !== undefined) params.set("unit", String(unit));
  if (state !== "all") params.set("state", state);
  if (search.trim()) params.set("search", search.trim());
  return getJson<{ items: Entry[] }>(`/api/entries?${params}`);
}

export function getEntry(entryId: number, book = "N2") {
    return getJson<Entry>(`/api/entries/${entryId}?book=${encodeURIComponent(book)}`);
}

export function getLegacyMarkSeed() {
  return getJson<{items: Array<{item_uuid: string; known: boolean; flagged: boolean}>}>("/api/study/legacy-seed");
}

export function resolveReviewEntries(items: Array<{
  item_uuid: string;
  preferred_book_code?: string;
  preferred_source_index?: number;
}>) {
  return getJson<{items: Entry[]}>("/api/study/resolve", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({items}),
  });
}

export function getStarredSentences(book = "N2", unit?: number) {
  const params = new URLSearchParams({ book });
  if (unit !== undefined) params.set("unit", String(unit));
  return getJson<{ items: StarredSentence[] }>(`/api/starred-sentences?${params}`);
}

export function updateMark(entryId: number, mark: Pick<Mark, "known" | "flagged">, book = "N2") {
  return getJson<{ mark: Mark }>(`/api/marks/${entryId}?book=${encodeURIComponent(book)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(mark),
  });
}

export function updateExampleStar(entryId: number, position: number, starred: boolean, book = "N2") {
  return getJson<{ starred: boolean }>(
    `/api/entries/${entryId}/examples/${position}/star?book=${encodeURIComponent(book)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ starred }),
    },
  );
}

export function exportUnitFlaggedAudio(unitNumber: number, book = "N2") {
  return getJson<{ audio_url: string; file_name?: string; unit: number; word_count: number }>(
    `/api/units/${unitNumber}/flagged-audio?book=${encodeURIComponent(book)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    },
  );
}
