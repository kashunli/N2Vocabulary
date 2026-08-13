export const STUDY_STATE_KEY = "n2-word-service:study-state:v1";
export const STUDY_STATE_VERSION = 1;
export const LEGACY_MIGRATION_KEY = "n2-word-service:study-state:legacy-migrated:v1";
export const GUEST_ARCHIVE_PREFIX = `${STUDY_STATE_KEY}:import-archive:`;
const REVIEW_ENROLLMENT_DELAY_MS = 24 * 60 * 60 * 1000;

function initialReviewDueAt(completedAt) {
  const date = new Date(completedAt);
  if (!Number.isFinite(date.getTime())) throw new Error("completedAt must be a valid timestamp");
  return new Date(date.getTime() + REVIEW_ENROLLMENT_DELAY_MS).toISOString();
}

export function emptyStudySnapshot() {
  return {version: STUDY_STATE_VERSION, updated_at: new Date(0).toISOString(), cards: {}};
}

function optionalIso(value) {
  if (typeof value !== "string" || !Number.isFinite(Date.parse(value))) return undefined;
  return new Date(value).toISOString();
}

function normalizeCard(value, key) {
  if (!value || typeof value !== "object") return null;
  const itemUuid = typeof value.item_uuid === "string" ? value.item_uuid.trim() : key;
  if (!itemUuid || itemUuid !== key) return null;
  return {
    item_uuid: itemUuid,
    known: value.known === true,
    flagged: value.flagged === true,
    enrolled_at: optionalIso(value.enrolled_at),
    due_at: optionalIso(value.due_at),
    last_played_at: optionalIso(value.last_played_at),
    preferred_book_code: typeof value.preferred_book_code === "string" ? value.preferred_book_code : undefined,
    preferred_source_index: Number.isInteger(value.preferred_source_index) ? value.preferred_source_index : undefined,
    updated_at: optionalIso(value.updated_at) || new Date(0).toISOString(),
  };
}

export function normalizeStudySnapshot(value) {
  const result = emptyStudySnapshot();
  if (!value || typeof value !== "object" || value.version !== STUDY_STATE_VERSION) return result;
  if (value.cards && typeof value.cards === "object") {
    for (const [key, candidate] of Object.entries(value.cards)) {
      const card = normalizeCard(candidate, key);
      if (card) result.cards[key] = card;
    }
  }
  result.updated_at = optionalIso(value.updated_at) || result.updated_at;
  return result;
}

export class LocalStudyStateStore {
  constructor(storage = window.localStorage, now = () => new Date()) {
    this.storage = storage;
    this.now = now;
    this.listeners = new Set();
    this.snapshot = this.read();
    this.onStorage = event => {
      if (event.key !== STUDY_STATE_KEY) return;
      this.snapshot = this.read();
      this.emit();
    };
    if (typeof window !== "undefined") window.addEventListener("storage", this.onStorage);
  }

  read() {
    const raw = this.storage.getItem(STUDY_STATE_KEY);
    if (!raw) return emptyStudySnapshot();
    try {
      return normalizeStudySnapshot(JSON.parse(raw));
    } catch {
      const suffix = this.now().toISOString().replaceAll(":", "-");
      this.storage.setItem(`${STUDY_STATE_KEY}:malformed:${suffix}`, raw);
      this.storage.removeItem(STUDY_STATE_KEY);
      return emptyStudySnapshot();
    }
  }

  load() { return this.snapshot; }

  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  emit() { for (const listener of this.listeners) listener(this.snapshot); }

  commit(cards) {
    const updatedAt = this.now().toISOString();
    this.snapshot = {version: STUDY_STATE_VERSION, updated_at: updatedAt, cards};
    this.storage.setItem(STUDY_STATE_KEY, JSON.stringify(this.snapshot));
    this.emit();
    return this.snapshot;
  }

  seedLegacy(items) {
    if (this.storage.getItem(LEGACY_MIGRATION_KEY)) return this.snapshot;
    const now = this.now().toISOString();
    const cards = {...this.snapshot.cards};
    for (const item of items) {
      if (!item?.item_uuid || cards[item.item_uuid]) continue;
      cards[item.item_uuid] = {
        item_uuid: item.item_uuid,
        known: item.known === true,
        flagged: item.flagged === true,
        updated_at: now,
      };
    }
    this.commit(cards);
    this.storage.setItem(LEGACY_MIGRATION_KEY, now);
    return this.snapshot;
  }

  async setMark(itemUuid, mark) {
    const now = this.now().toISOString();
    const current = this.snapshot.cards[itemUuid] || {item_uuid: itemUuid, known: false, flagged: false};
    return this.commit({...this.snapshot.cards, [itemUuid]: {...current, ...mark, updated_at: now}}).cards[itemUuid];
  }

  async recordPlayed(entry) {
    const now = this.now().toISOString();
    const current = this.snapshot.cards[entry.item_uuid] || {
      item_uuid: entry.item_uuid, known: false, flagged: false,
    };
    const enrolledAt = current.enrolled_at || now;
    const next = {
      ...current,
      enrolled_at: enrolledAt,
      due_at: current.due_at || initialReviewDueAt(now),
      last_played_at: now,
      preferred_book_code: entry.book_code,
      preferred_source_index: entry.source_index,
      updated_at: now,
    };
    return this.commit({...this.snapshot.cards, [entry.item_uuid]: next}).cards[entry.item_uuid];
  }

  dueCards(at = this.now()) {
    const timestamp = at.getTime();
    return Object.values(this.snapshot.cards)
      .filter(card => card.due_at && Date.parse(card.due_at) <= timestamp)
      .sort((left, right) => left.due_at.localeCompare(right.due_at)
        || (left.enrolled_at || "").localeCompare(right.enrolled_at || "")
        || left.item_uuid.localeCompare(right.item_uuid));
  }

  exportSnapshot() { return JSON.parse(JSON.stringify(this.snapshot)); }

  archiveSnapshot(importId, checksum) {
    for (let index = this.storage.length - 1; index >= 0; index -= 1) {
      const key = this.storage.key(index);
      if (key?.startsWith(GUEST_ARCHIVE_PREFIX)) this.storage.removeItem(key);
    }
    const key = `${GUEST_ARCHIVE_PREFIX}${this.now().toISOString().replaceAll(":", "-")}:${importId}`;
    this.storage.setItem(key, JSON.stringify({checksum, snapshot: this.snapshot}));
    return key;
  }

  clearActive() {
    this.storage.removeItem(STUDY_STATE_KEY);
    this.snapshot = emptyStudySnapshot();
    this.emit();
  }
}
