import assert from "node:assert/strict";
import test from "node:test";

import {LEGACY_MIGRATION_KEY, LocalStudyStateStore, STUDY_STATE_KEY} from "./localStudyState.mjs";

class MemoryStorage {
  constructor() { this.values = new Map(); }
  getItem(key) { return this.values.get(key) ?? null; }
  setItem(key, value) { this.values.set(key, String(value)); }
  removeItem(key) { this.values.delete(key); }
}

const now = () => new Date("2026-08-13T00:00:00.000Z");

test("legacy known cards are due now while flagged-only cards stay unenrolled", () => {
  const storage = new MemoryStorage();
  const store = new LocalStudyStateStore(storage, now);
  store.seedLegacy([
    {item_uuid: "known", known: true, flagged: false},
    {item_uuid: "flagged", known: false, flagged: true},
  ]);
  assert.deepEqual(store.dueCards().map(card => card.item_uuid), ["known"]);
  assert.equal(store.load().cards.flagged.enrolled_at, undefined);
  assert.ok(storage.getItem(LEGACY_MIGRATION_KEY));
});

test("complete play enrolls once and later plays update only source and played time", () => {
  const storage = new MemoryStorage();
  let date = new Date("2026-08-13T00:00:00.000Z");
  const store = new LocalStudyStateStore(storage, () => date);
  store.recordPlayed({item_uuid: "shared", book_code: "N2", source_index: 4});
  const first = store.load().cards.shared;
  date = new Date("2026-08-20T00:00:00.000Z");
  store.recordPlayed({item_uuid: "shared", book_code: "GWB_N2", source_index: 44});
  const replayed = store.load().cards.shared;
  assert.equal(replayed.due_at, first.due_at);
  assert.equal(replayed.preferred_book_code, "GWB_N2");
  assert.equal(replayed.preferred_source_index, 44);
});

test("grades update schedule and apply positive tags without toggling", () => {
  const store = new LocalStudyStateStore(new MemoryStorage(), now);
  store.recordPlayed({item_uuid: "card", book_code: "N2", source_index: 1});
  assert.equal(store.grade("card", "hard").flagged, true);
  assert.equal(store.grade("card", "hard").flagged, true);
  const good = store.grade("card", "good");
  assert.equal(good.known, true);
  assert.equal(good.flagged, true);
});

test("malformed state is archived before recovery", () => {
  const storage = new MemoryStorage();
  storage.setItem(STUDY_STATE_KEY, "{bad");
  const store = new LocalStudyStateStore(storage, now);
  assert.deepEqual(store.load().cards, {});
  assert.ok([...storage.values.keys()].some(key => key.includes(":malformed:")));
});
