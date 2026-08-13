import assert from "node:assert/strict";
import test from "node:test";

import {LEGACY_MIGRATION_KEY, LocalStudyStateStore, STUDY_STATE_KEY} from "./localStudyState.mjs";

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

test("complete play enrolls once and later plays update only source and played time", async () => {
  const storage = new MemoryStorage();
  let date = new Date("2026-08-13T00:00:00.000Z");
  const store = new LocalStudyStateStore(storage, () => date);
  await store.recordPlayed({item_uuid: "shared", book_code: "N2", source_index: 4});
  const first = store.load().cards.shared;
  date = new Date("2026-08-20T00:00:00.000Z");
  await store.recordPlayed({item_uuid: "shared", book_code: "GWB_N2", source_index: 44});
  const replayed = store.load().cards.shared;
  assert.equal(replayed.due_at, first.due_at);
  assert.equal(replayed.preferred_book_code, "GWB_N2");
  assert.equal(replayed.preferred_source_index, 44);
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
