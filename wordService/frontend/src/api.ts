import type { Entry, UnitSummary } from "./types";

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(await response.text() || `Request failed: ${response.status}`);
  return response.json() as Promise<T>;
}

export function getUnits(book = "N2") {
  return getJson<{ items: UnitSummary[] }>(`/api/units?book=${encodeURIComponent(book)}`);
}

export function getEntries(book = "N2", unit?: number) {
  const params = new URLSearchParams({ book });
  if (unit) params.set("unit", String(unit));
  return getJson<{ items: Entry[] }>(`/api/entries?${params}`);
}

export function getEntry(entryId: number, book = "N2") {
  return getJson<Entry>(`/api/entries/${entryId}?book=${encodeURIComponent(book)}`);
}
