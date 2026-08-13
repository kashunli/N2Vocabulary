import { state } from "./state.js";

export async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.json();
}

export function withBookParam(path, params = new URLSearchParams()) {
  params.set("book", state.selectedBook);
  return `${path}?${params.toString()}`;
}

export function fetchBooks() {
  return fetchJson("/api/books");
}

export function fetchSummary() {
  return fetchJson(withBookParam("/api/summary"));
}

export function fetchUnits() {
  return fetchJson(withBookParam("/api/units"));
}

export function fetchEntries(params) {
  return fetchJson(withBookParam("/api/entries", params));
}

export function fetchLegacyMarkSeed() {
  return fetchJson("/api/study/legacy-seed");
}

export function fetchStarredSentences(params) {
  return fetchJson(withBookParam("/api/starred-sentences", params));
}

export function fetchEntry(entryId) {
  return fetchJson(withBookParam(`/api/entries/${entryId}`));
}

export function updateMark(entryId, mark) {
  return fetchJson(withBookParam(`/api/marks/${entryId}`), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(mark),
  });
}

export function updateExampleStar(entryId, position, starred) {
  return fetchJson(withBookParam(`/api/entries/${entryId}/examples/${position}/star`), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({starred}),
  });
}

export function generateEntryAudio(entryId) {
  return fetchJson(withBookParam(`/api/entries/${entryId}/audio`), {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: "{}",
  });
}

export function generateExampleAudio(entryId, position) {
  return fetchJson(withBookParam(`/api/entries/${entryId}/examples/${position}/audio`), {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: "{}",
  });
}

export function exportUnitFlaggedAudio(unitNumber) {
  return fetchJson(withBookParam(`/api/units/${unitNumber}/flagged-audio`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
}
