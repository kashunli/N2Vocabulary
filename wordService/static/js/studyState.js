const STUDY_STATE_KEY = "n2-word-service:study-state:v1";
const LEGACY_MIGRATION_KEY = "n2-word-service:study-state:legacy-migrated:v1";

function readSnapshot() {
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
  return {known: !!card?.known, flagged: !!card?.flagged, updated_at: card?.updated_at};
}

export function setStudyMark(itemUuid, mark) {
  const snapshot = readSnapshot();
  const now = new Date().toISOString();
  const current = snapshot.cards[itemUuid] || {item_uuid: itemUuid, good_step: 0};
  snapshot.cards[itemUuid] = {...current, known: !!mark.known, flagged: !!mark.flagged, updated_at: now};
  snapshot.updated_at = now;
  window.localStorage.setItem(STUDY_STATE_KEY, JSON.stringify(snapshot));
  return snapshot.cards[itemUuid];
}

export function applyStudyMarks(items, filterState = "all") {
  return items.map(entry => ({...entry, mark: studyMark(entry.item_uuid)})).filter(entry => (
    filterState === "all"
    || (filterState === "known" && entry.mark.known)
    || (filterState === "flagged" && entry.mark.flagged)
    || (filterState === "unmarked" && !entry.mark.known && !entry.mark.flagged)
  ));
}

export function seedLegacyStudyMarks(items) {
  if (window.localStorage.getItem(LEGACY_MIGRATION_KEY)) return;
  const snapshot = readSnapshot();
  const now = new Date().toISOString();
  items.forEach(item => {
    if (!item.item_uuid || snapshot.cards[item.item_uuid]) return;
    snapshot.cards[item.item_uuid] = {
      item_uuid: item.item_uuid, known: !!item.known, flagged: !!item.flagged,
      enrolled_at: item.known ? now : undefined, due_at: item.known ? now : undefined,
      good_step: 0, updated_at: now,
    };
  });
  snapshot.updated_at = now;
  window.localStorage.setItem(STUDY_STATE_KEY, JSON.stringify(snapshot));
  window.localStorage.setItem(LEGACY_MIGRATION_KEY, now);
}
