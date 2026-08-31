import type {
  BookSummary,
  Entry,
  UnitSummary,
  VocabularySummary,
} from "./types";
import type { MarkStatus } from "./features/study/markStatus";
import type {ImportedMark, ReviewCompletionResult, StudyCardState, StudySnapshot} from "./features/study/studyStateTypes";

const MARKED_WORDS_FILE_FORMAT = "n2-word-service-marked-words";

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
  book: string,
  contentRevision: string,
  unit: number,
  state: "all" | "unmarked" | "known" | "flagged" = "all",
) {
  const params = new URLSearchParams({
    book,
    unit: String(unit),
    v: contentRevision,
  });
  if (state !== "all") params.set("state", state);
  return getJson<{ items: Entry[] }>(`/api/entries?${params}`);
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
export function importAccountMarks(csrfToken: string, items: ImportedMark[]) {
  return getJson<StudySnapshot>("/api/study/import-marks", {method: "POST", headers: {"Content-Type": "application/json", "X-CSRF-Token": csrfToken}, body: JSON.stringify({format: MARKED_WORDS_FILE_FORMAT, version: 1, items})});
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
