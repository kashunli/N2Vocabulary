import type {
  BookSummary,
  Entry,
  Mark,
  UnitSummary,
  VocabularySummary,
} from "./types";
import type { MarkStatus } from "./features/study/markStatus";
import type {ReviewCompletionResult, StudyCardState, StudySnapshot} from "./features/study/studyStateTypes";

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

export interface AuthSession { user: {id: number; email: string}; csrf_token: string }

export function getCurrentUser() { return getJson<AuthSession>("/api/auth/me"); }
export function registerAccount(email: string, password: string) {
  return getJson<AuthSession>("/api/auth/register", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({email, password})});
}
export function loginAccount(email: string, password: string) {
  return getJson<AuthSession>("/api/auth/login", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({email, password})});
}
export function logoutAccount(csrfToken: string) {
  return getJson<{ok: boolean}>("/api/auth/logout", {method: "POST", headers: {"Content-Type": "application/json", "X-CSRF-Token": csrfToken}, body: "{}"});
}
export function getAccountStudyState() { return getJson<StudySnapshot>("/api/study/state"); }
export function updateAccountMarks(csrfToken: string, itemUuid: string, status: MarkStatus) {
  return getJson<{card: StudyCardState}>(`/api/study/cards/${encodeURIComponent(itemUuid)}/marks`, {method: "PUT", headers: {"Content-Type": "application/json", "X-CSRF-Token": csrfToken}, body: JSON.stringify({status})});
}
export function recordAccountPlayback(csrfToken: string, entry: {item_uuid: string; book_code: string; source_index: number}) {
  return getJson<{card: StudyCardState}>(`/api/study/cards/${encodeURIComponent(entry.item_uuid)}/played`, {method: "POST", headers: {"Content-Type": "application/json", "X-CSRF-Token": csrfToken}, body: JSON.stringify({preferred_book_code: entry.book_code, preferred_source_index: entry.source_index})});
}
export async function completeAccountReview(csrfToken: string, entry: {item_uuid: string; book_code: string; source_index: number}, expectedDueAt: string): Promise<ReviewCompletionResult> {
  const response = await fetch(`/api/study/cards/${encodeURIComponent(entry.item_uuid)}/review-complete`, {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-CSRF-Token": csrfToken},
    body: JSON.stringify({expected_due_at: expectedDueAt, preferred_book_code: entry.book_code, preferred_source_index: entry.source_index}),
  });
  const payload = await response.json().catch(() => ({})) as {card?: StudyCardState; error?: string};
  if (response.status === 409) return {completed: false, card: payload.card};
  if (!response.ok) throw new Error(payload.error || `Request failed: ${response.status}`);
  return {completed: true, card: payload.card};
}
export function importGuestStudyState(csrfToken: string, payload: {version: number; import_id: string; snapshot_checksum: string; cards: StudySnapshot["cards"]}) {
  return getJson<StudySnapshot>("/api/study/import-guest", {method: "POST", headers: {"Content-Type": "application/json", "X-CSRF-Token": csrfToken}, body: JSON.stringify(payload)});
}

export function updateMark(entryId: number, mark: Pick<Mark, "known" | "flagged">, book = "N2") {
  return getJson<{ mark: Mark }>(`/api/marks/${entryId}?book=${encodeURIComponent(book)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(mark),
  });
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
