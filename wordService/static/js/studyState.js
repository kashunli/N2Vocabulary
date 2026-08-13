const STUDY_STATE_KEY = "n2-word-service:study-state:v1";
const STUDY_STATE_VERSION = 2;
const LEGACY_MIGRATION_KEY = "n2-word-service:study-state:legacy-migrated:v1";
const PRE_SPACED_REVIEW_ARCHIVE_PREFIX = `${STUDY_STATE_KEY}:pre-spaced-review:`;
const DAY_MS = 24 * 60 * 60 * 1000;
let accountSnapshot = null;
let csrfToken = "";

function optionalIso(value) {
  return typeof value === "string" && Number.isFinite(Date.parse(value))
    ? new Date(value).toISOString()
    : undefined;
}

function emptySnapshot() {
  return {version: STUDY_STATE_VERSION, updated_at: new Date(0).toISOString(), cards: {}};
}

function normalizeCard(value, key, {stripSchedule = false} = {}) {
  if (!value || typeof value !== "object") return null;
  const itemUuid = typeof value.item_uuid === "string" ? value.item_uuid.trim() : key;
  if (!itemUuid || itemUuid !== key) return null;
  return {
    item_uuid: itemUuid,
    known: value.known === true,
    flagged: value.flagged === true,
    ...(stripSchedule ? {} : {enrolled_at: optionalIso(value.enrolled_at), due_at: optionalIso(value.due_at)}),
    review_level: stripSchedule ? 0 : (Number.isInteger(value.review_level) && value.review_level >= 0 ? value.review_level : 0),
    ...(stripSchedule ? {} : {last_reviewed_at: optionalIso(value.last_reviewed_at)}),
    last_played_at: optionalIso(value.last_played_at),
    preferred_book_code: typeof value.preferred_book_code === "string" ? value.preferred_book_code : undefined,
    preferred_source_index: Number.isInteger(value.preferred_source_index) ? value.preferred_source_index : undefined,
    updated_at: optionalIso(value.updated_at) || new Date(0).toISOString(),
  };
}

function normalizeSnapshot(value, {stripSchedule = false} = {}) {
  const result = emptySnapshot();
  if (!value || typeof value !== "object" || !value.cards || typeof value.cards !== "object") return result;
  for (const [key, candidate] of Object.entries(value.cards)) {
    const card = normalizeCard(candidate, key, {stripSchedule});
    if (card) result.cards[key] = card;
  }
  result.updated_at = optionalIso(value.updated_at) || result.updated_at;
  return result;
}

function saveLocalSnapshot(snapshot) {
  window.localStorage.setItem(STUDY_STATE_KEY, JSON.stringify(snapshot));
  return snapshot;
}

export async function initializeStudyState() {
  const response = await fetch("/api/auth/me");
  if (!response.ok) return false;
  const auth = await response.json();
  const stateResponse = await fetch("/api/study/state");
  if (!stateResponse.ok) throw new Error("Could not load account study state.");
  csrfToken = auth.csrf_token;
  accountSnapshot = await stateResponse.json();
  return true;
}

function readSnapshot() {
  if (accountSnapshot) return accountSnapshot;
  try {
    const raw = window.localStorage.getItem(STUDY_STATE_KEY);
    if (!raw) return emptySnapshot();
    const value = JSON.parse(raw);
    if (value?.version === STUDY_STATE_VERSION) return normalizeSnapshot(value);
    if (value?.version === 1) {
      const suffix = new Date().toISOString().replaceAll(":", "-");
      window.localStorage.setItem(`${PRE_SPACED_REVIEW_ARCHIVE_PREFIX}${suffix}`, raw);
      return saveLocalSnapshot(normalizeSnapshot(value, {stripSchedule: true}));
    }
  } catch {
    // The React store owns malformed-state archival. Classic starts safely
    // from an empty snapshot when an unrelated stale payload is unreadable.
  }
  return emptySnapshot();
}

function updateSnapshot(card) {
  if (accountSnapshot) {
    accountSnapshot = {...accountSnapshot, updated_at: card.updated_at, cards: {...accountSnapshot.cards, [card.item_uuid]: card}};
    return card;
  }
  const snapshot = readSnapshot();
  snapshot.cards[card.item_uuid] = card;
  snapshot.updated_at = card.updated_at;
  saveLocalSnapshot(snapshot);
  return card;
}

export function nextReviewDueAt(completedAt, reviewLevel) {
  const completed = new Date(completedAt);
  if (!Number.isFinite(completed.getTime()) || !Number.isInteger(reviewLevel) || reviewLevel < 0) {
    throw new Error("review completion must have a valid time and level");
  }
  const next = completed.getTime() + 2 ** reviewLevel * DAY_MS;
  if (!Number.isFinite(next) || Math.abs(next) > 8.64e15) throw new Error("review interval is too large");
  return new Date(next).toISOString();
}

export function studyMark(itemUuid) {
  const card = readSnapshot().cards[itemUuid];
  return {known: !!card?.known, flagged: !!card?.flagged, due_at: card?.due_at, review_level: card?.review_level, last_reviewed_at: card?.last_reviewed_at, updated_at: card?.updated_at};
}

export async function setStudyMark(itemUuid, mark) {
  if (accountSnapshot) {
    const response = await fetch(`/api/study/cards/${encodeURIComponent(itemUuid)}/marks`, {
      method: "PUT", headers: {"Content-Type": "application/json", "X-CSRF-Token": csrfToken}, body: JSON.stringify(mark),
    });
    if (!response.ok) throw new Error(await response.text() || "Could not update account mark.");
    return updateSnapshot((await response.json()).card);
  }
  const snapshot = readSnapshot();
  const now = new Date().toISOString();
  const current = snapshot.cards[itemUuid] || {item_uuid: itemUuid, review_level: 0};
  return updateSnapshot({...current, known: !!mark.known, flagged: !!mark.flagged, updated_at: now});
}

export async function recordStudyCompleted(entry) {
  if (accountSnapshot) {
    const response = await fetch(`/api/study/cards/${encodeURIComponent(entry.item_uuid)}/played`, {
      method: "POST", headers: {"Content-Type": "application/json", "X-CSRF-Token": csrfToken}, body: JSON.stringify({preferred_book_code: entry.book_code, preferred_source_index: entry.source_index}),
    });
    if (!response.ok) throw new Error(await response.text() || "Could not save study playback.");
    return updateSnapshot((await response.json()).card);
  }
  const snapshot = readSnapshot();
  const now = new Date().toISOString();
  const current = snapshot.cards[entry.item_uuid] || {item_uuid: entry.item_uuid, known: false, flagged: false, review_level: 0};
  return updateSnapshot({...current, enrolled_at: current.enrolled_at || now, due_at: current.due_at || nextReviewDueAt(now, 0), review_level: current.due_at ? current.review_level : 0, last_played_at: now, preferred_book_code: entry.book_code, preferred_source_index: entry.source_index, updated_at: now});
}

export async function completeStudyReview(entry, expectedDueAt) {
  if (accountSnapshot) {
    const response = await fetch(`/api/study/cards/${encodeURIComponent(entry.item_uuid)}/review-complete`, {
      method: "POST", headers: {"Content-Type": "application/json", "X-CSRF-Token": csrfToken}, body: JSON.stringify({expected_due_at: expectedDueAt, preferred_book_code: entry.book_code, preferred_source_index: entry.source_index}),
    });
    const payload = await response.json().catch(() => ({}));
    if (response.status === 409) {
      if (payload.card) updateSnapshot(payload.card);
      return {completed: false, card: payload.card};
    }
    if (!response.ok) throw new Error(payload.error || "Could not save review completion.");
    return {completed: true, card: updateSnapshot(payload.card)};
  }
  const current = readSnapshot().cards[entry.item_uuid];
  const now = new Date().toISOString();
  if (!current || current.due_at !== expectedDueAt || Date.parse(expectedDueAt) > Date.parse(now)) return {completed: false, card: current};
  const reviewLevel = current.review_level + 1;
  return {completed: true, card: updateSnapshot({...current, review_level: reviewLevel, due_at: nextReviewDueAt(now, reviewLevel), last_reviewed_at: now, last_played_at: now, preferred_book_code: entry.book_code, preferred_source_index: entry.source_index, updated_at: now})};
}

export function summarizeStudyMarks(items) {
  let known = 0; let flagged = 0; let review = 0;
  for (const item of items) {
    const mark = studyMark(item.item_uuid);
    known += Number(mark.known);
    flagged += Number(mark.flagged);
    review += Number(isReviewDue(mark));
  }
  return {known, flagged, review, unmarked: items.length - new Set(items.filter(item => { const mark = studyMark(item.item_uuid); return mark.known || mark.flagged; }).map(item => item.entry_id)).size};
}

export function isReviewDue(mark, now = Date.now()) {
  const timestamp = Date.parse(mark?.due_at || "");
  return Number.isFinite(timestamp) && timestamp <= now;
}

export function startReviewSession(items, scopeKey, now = Date.now()) {
  const expectedDueAtByItemUuid = {};
  items.forEach(item => {
    const mark = studyMark(item.item_uuid);
    if (isReviewDue(mark, now) && mark.due_at) expectedDueAtByItemUuid[item.item_uuid] = mark.due_at;
  });
  return {scopeKey, expectedDueAtByItemUuid, completedByItemUuid: {}, completingItemUuids: new Set()};
}

export function applyStudyMarks(items, filterState = "all", reviewSession) {
  return items.map(entry => ({...entry, mark: studyMark(entry.item_uuid)})).filter(entry => (
    filterState === "all"
    || (filterState === "review" && (reviewSession
      ? Object.hasOwn(reviewSession.expectedDueAtByItemUuid, entry.item_uuid)
      : isReviewDue(entry.mark)))
    || (filterState === "known" && entry.mark.known)
    || (filterState === "flagged" && entry.mark.flagged)
    || (filterState === "unmarked" && !entry.mark.known && !entry.mark.flagged)
  )).map(entry => ({...entry, review_completed: !!reviewSession?.completedByItemUuid[entry.item_uuid]}));
}

export function seedLegacyStudyMarks(items) {
  if (accountSnapshot || window.localStorage.getItem(LEGACY_MIGRATION_KEY)) return;
  const snapshot = readSnapshot();
  const now = new Date().toISOString();
  items.forEach(item => {
    if (!item.item_uuid || snapshot.cards[item.item_uuid]) return;
    snapshot.cards[item.item_uuid] = {item_uuid: item.item_uuid, known: !!item.known, flagged: !!item.flagged, review_level: 0, updated_at: now};
  });
  snapshot.updated_at = now;
  saveLocalSnapshot(snapshot);
  window.localStorage.setItem(LEGACY_MIGRATION_KEY, now);
}
