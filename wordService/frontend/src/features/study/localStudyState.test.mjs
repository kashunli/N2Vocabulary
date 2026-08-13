import assert from "node:assert/strict";
import test from "node:test";

import {LEGACY_MIGRATION_KEY, LocalStudyStateStore, PRE_SPACED_REVIEW_ARCHIVE_PREFIX, STUDY_STATE_KEY, STUDY_STATE_VERSION, nextReviewDueAt} from "./localStudyState.mjs";

class MemoryStorage {
  constructor() { this.values = new Map(); }
  get length() { return this.values.size; }
  key(index) { return [...this.values.keys()][index] ?? null; }
  getItem(key) { return this.values.get(key) ?? null; }
  setItem(key, value) { this.values.set(key, String(value)); }
  removeItem(key) { this.values.delete(key); }
}

const now = () => new Date("2026-08-13T00:00:00.000Z");

test("legacy marks stay independent from review enrollment", () => {
  const storage = new MemoryStorage();
  const store = new LocalStudyStateStore(storage, now);
  store.seedLegacy([
    {item_uuid: "known", known: true, flagged: false},
    {item_uuid: "flagged", known: false, flagged: true},
  ]);
  assert.equal(store.load().cards.known.enrolled_at, undefined);
  assert.equal(store.load().cards.known.due_at, undefined);
  assert.equal(store.load().cards.flagged.enrolled_at, undefined);
  assert.ok(storage.getItem(LEGACY_MIGRATION_KEY));
});

test("normal study enrolls at level zero and later playback does not postpone it", async () => {
  const storage = new MemoryStorage();
  let date = new Date("2026-08-13T00:00:00.000Z");
  const store = new LocalStudyStateStore(storage, () => date);
  await store.recordStudyCompleted({item_uuid: "shared", book_code: "N2", source_index: 4});
  const first = store.load().cards.shared;
  date = new Date("2026-08-20T00:00:00.000Z");
  await store.recordStudyCompleted({item_uuid: "shared", book_code: "GWB_N2", source_index: 44});
  const replayed = store.load().cards.shared;
  assert.equal(replayed.due_at, first.due_at);
  assert.equal(replayed.review_level, 0);
  assert.equal(replayed.preferred_book_code, "GWB_N2");
  assert.equal(replayed.preferred_source_index, 44);
});

test("review completion advances once and replaying its old due time conflicts", async () => {
  const storage = new MemoryStorage();
  let date = new Date("2026-08-13T00:00:00.000Z");
  const store = new LocalStudyStateStore(storage, () => date);
  await store.recordStudyCompleted({item_uuid: "card", book_code: "N2", source_index: 4});
  const expectedDueAt = store.load().cards.card.due_at;
  date = new Date("2026-08-14T00:00:00.000Z");
  const result = await store.completeReview({item_uuid: "card", book_code: "N2", source_index: 4}, expectedDueAt);
  assert.equal(result.completed, true);
  assert.equal(result.card.review_level, 1);
  assert.equal(result.card.due_at, "2026-08-16T00:00:00.000Z");
  assert.equal((await store.completeReview({item_uuid: "card", book_code: "N2", source_index: 4}, expectedDueAt)).completed, false);
});

test("review intervals double and reject an unrepresentable level", () => {
  assert.equal(nextReviewDueAt("2026-08-13T00:00:00.000Z", 0), "2026-08-14T00:00:00.000Z");
  assert.equal(nextReviewDueAt("2026-08-13T00:00:00.000Z", 5), "2026-09-14T00:00:00.000Z");
  assert.throws(() => nextReviewDueAt("2026-08-13T00:00:00.000Z", 63));
});

test("version-one state is archived and migrated without its old schedule", () => {
  const storage = new MemoryStorage();
  storage.setItem(STUDY_STATE_KEY, JSON.stringify({
    version: 1,
    updated_at: "2026-08-13T00:00:00.000Z",
    cards: {card: {item_uuid: "card", known: true, flagged: true, enrolled_at: "2026-08-01T00:00:00.000Z", due_at: "2026-08-02T00:00:00.000Z", good_step: 4, updated_at: "2026-08-13T00:00:00.000Z"}},
  }));
  const store = new LocalStudyStateStore(storage, now);
  const card = store.load().cards.card;
  assert.equal(store.load().version, STUDY_STATE_VERSION);
  assert.equal(card.known, true);
  assert.equal(card.flagged, true);
  assert.equal(card.due_at, undefined);
  assert.equal(card.review_level, 0);
  assert.ok([...storage.values.keys()].some(key => key.startsWith(PRE_SPACED_REVIEW_ARCHIVE_PREFIX)));
});

test("marking a card does not enroll or schedule it", async () => {
  const store = new LocalStudyStateStore(new MemoryStorage(), now);
  const marked = await store.setMark("card", {known: true, flagged: true});
  assert.equal(marked.known, true);
  assert.equal(marked.flagged, true);
  assert.equal(marked.enrolled_at, undefined);
  assert.equal(marked.due_at, undefined);
});

test("malformed state is archived before recovery", () => {
  const storage = new MemoryStorage();
  storage.setItem(STUDY_STATE_KEY, "{bad");
  const store = new LocalStudyStateStore(storage, now);
  assert.deepEqual(store.load().cards, {});
  assert.ok([...storage.values.keys()].some(key => key.includes(":malformed:")));
});

test("guest import archive is retained when active state is cleared", async () => {
  const storage = new MemoryStorage();
  const store = new LocalStudyStateStore(storage, now);
  await store.setMark("card", {known: true, flagged: false});
  const archiveKey = store.archiveSnapshot("import-one", "checksum");
  store.clearActive();
  assert.equal(storage.getItem(STUDY_STATE_KEY), null);
  assert.equal(JSON.parse(storage.getItem(archiveKey)).snapshot.cards.card.known, true);
});
