const STUDY_STATE_KEY = "n2-word-service:study-state:v1";
const LEGACY_MIGRATION_KEY = "n2-word-service:study-state:legacy-migrated:v1";
let accountSnapshot = null;
let csrfToken = "";

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
    const value = JSON.parse(window.localStorage.getItem(STUDY_STATE_KEY) || "null");
    return value && value.version === 1 && value.cards && typeof value.cards === "object"
      ? value
      : {version: 1, cards: {}};
  } catch {
    return {version: 1, cards: {}};
  }
}

export function studyMark(itemUuid) {
  const card = readSnapshot().cards[itemUuid];
  return {known: !!card?.known, flagged: !!card?.flagged, due_at: card?.due_at, updated_at: card?.updated_at};
}

export async function setStudyMark(itemUuid, mark) {
  if (accountSnapshot) {
    const response = await fetch(`/api/study/cards/${encodeURIComponent(itemUuid)}/marks`, {
      method: "PUT", headers: {"Content-Type": "application/json", "X-CSRF-Token": csrfToken}, body: JSON.stringify(mark),
    });
    if (!response.ok) throw new Error(await response.text() || "Could not update account mark.");
    const {card} = await response.json();
    accountSnapshot = {...accountSnapshot, updated_at: card.updated_at, cards: {...accountSnapshot.cards, [itemUuid]: card}};
    return card;
  }
  const snapshot = readSnapshot();
  const now = new Date().toISOString();
  const current = snapshot.cards[itemUuid] || {item_uuid: itemUuid};
  snapshot.cards[itemUuid] = {...current, known: !!mark.known, flagged: !!mark.flagged, updated_at: now};
  snapshot.updated_at = now;
  window.localStorage.setItem(STUDY_STATE_KEY, JSON.stringify(snapshot));
  return snapshot.cards[itemUuid];
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

export function applyStudyMarks(items, filterState = "all") {
  return items.map(entry => ({...entry, mark: studyMark(entry.item_uuid)})).filter(entry => (
    filterState === "all"
    || (filterState === "review" && isReviewDue(entry.mark))
    || (filterState === "known" && entry.mark.known)
    || (filterState === "flagged" && entry.mark.flagged)
    || (filterState === "unmarked" && !entry.mark.known && !entry.mark.flagged)
  ));
}

export function seedLegacyStudyMarks(items) {
  if (accountSnapshot) return;
  if (window.localStorage.getItem(LEGACY_MIGRATION_KEY)) return;
  const snapshot = readSnapshot();
  const now = new Date().toISOString();
  items.forEach(item => {
    if (!item.item_uuid || snapshot.cards[item.item_uuid]) return;
    snapshot.cards[item.item_uuid] = {
      item_uuid: item.item_uuid, known: !!item.known, flagged: !!item.flagged,
      updated_at: now,
    };
  });
  snapshot.updated_at = now;
  window.localStorage.setItem(STUDY_STATE_KEY, JSON.stringify(snapshot));
  window.localStorage.setItem(LEGACY_MIGRATION_KEY, now);
}
