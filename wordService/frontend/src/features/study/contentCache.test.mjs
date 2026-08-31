import assert from "node:assert/strict";
import test from "node:test";

import {
  CONTENT_CACHE_MAX_UNITS,
  CONTENT_CACHE_PREFIX,
  contentUnitKey,
  loadContentScope,
  pruneContentCache,
  readContentUnit,
  writeContentUnit,
} from "./contentCache.mjs";

class MemoryStorage {
  constructor() { this.values = new Map(); }
  get length() { return this.values.size; }
  key(index) { return [...this.values.keys()][index] ?? null; }
  getItem(key) { return this.values.get(key) ?? null; }
  setItem(key, value) { this.values.set(key, String(value)); }
  removeItem(key) { this.values.delete(key); }
}

const entriesFor = (unit) => [{entry_id: unit, item_uuid: `unit-${unit}`}];

test("unit entries are keyed by book, revision, and unit", () => {
  const storage = new MemoryStorage();
  writeContentUnit("GWB_N2", "rev-1", 3, entriesFor(3), storage, () => 1);
  assert.deepEqual(readContentUnit("GWB_N2", "rev-1", 3, storage), entriesFor(3));
  assert.equal(readContentUnit("GWB_N2", "rev-2", 3, storage), undefined);
  assert.equal(readContentUnit("GWB_N2", "rev-1", 4, storage), undefined);
  assert.ok(contentUnitKey("GWB_N2", "rev-1", 3).startsWith(`${CONTENT_CACHE_PREFIX}:`));
});

test("selected section fetches only that unit and then reuses local cache", async () => {
  const storage = new MemoryStorage();
  const requests = [];
  const load = () => loadContentScope({
    book: "GWB_N2",
    revision: "rev-1",
    selectedUnit: 2,
    units: [{number: 1}, {number: 2}],
    readUnit: (book, revision, unit) => readContentUnit(book, revision, unit, storage),
    writeUnit: (book, revision, unit, entries) => writeContentUnit(book, revision, unit, entries, storage),
    fetchUnit: async (unit) => { requests.push(unit); return entriesFor(unit); },
  });
  assert.deepEqual(await load(), entriesFor(2));
  assert.deepEqual(await load(), entriesFor(2));
  assert.deepEqual(requests, [2]);
});

test("all sections is assembled from cached and missing unit payloads", async () => {
  const storage = new MemoryStorage();
  writeContentUnit("N2", "rev", 1, entriesFor(1), storage);
  const requests = [];
  const entries = await loadContentScope({
    book: "N2",
    revision: "rev",
    selectedUnit: null,
    units: [{number: 1}, {number: 2}, {number: 3}],
    readUnit: (book, revision, unit) => readContentUnit(book, revision, unit, storage),
    writeUnit: (book, revision, unit, value) => writeContentUnit(book, revision, unit, value, storage),
    fetchUnit: async (unit) => { requests.push(unit); return entriesFor(unit); },
  });
  assert.deepEqual(requests.sort(), [2, 3]);
  assert.deepEqual(entries.map((entry) => entry.entry_id), [1, 2, 3]);
});

test("a new content revision cannot read the old unit cache", async () => {
  const storage = new MemoryStorage();
  writeContentUnit("N2", "old", 1, entriesFor(1), storage);
  const requests = [];
  await loadContentScope({
    book: "N2",
    revision: "new",
    selectedUnit: 1,
    units: [{number: 1}],
    readUnit: (book, revision, unit) => readContentUnit(book, revision, unit, storage),
    writeUnit: (book, revision, unit, value) => writeContentUnit(book, revision, unit, value, storage),
    fetchUnit: async (unit) => { requests.push(unit); return entriesFor(unit); },
  });
  assert.deepEqual(requests, [1]);
});

test("prune keeps only the most recently used unit payloads", () => {
  const storage = new MemoryStorage();
  for (let unit = 1; unit <= CONTENT_CACHE_MAX_UNITS + 1; unit += 1) {
    writeContentUnit("N2", "rev", unit, entriesFor(unit), storage, () => unit);
  }
  assert.equal(readContentUnit("N2", "rev", 1, storage), undefined);
  assert.ok(readContentUnit("N2", "rev", CONTENT_CACHE_MAX_UNITS + 1, storage));
  assert.ok(storage.values.size <= CONTENT_CACHE_MAX_UNITS + 1);
});

test("malformed data and quota failures degrade to a cache miss", () => {
  const storage = new MemoryStorage();
  storage.setItem(contentUnitKey("N2", "rev", 1), "not json");
  assert.equal(readContentUnit("N2", "rev", 1, storage), undefined);
  storage.setItem(contentUnitKey("N2", "rev", 1), JSON.stringify({items: []}));
  assert.equal(readContentUnit("N2", "rev", 1, storage), undefined);

  const full = new MemoryStorage();
  full.setItem = () => { throw new Error("quota"); };
  assert.doesNotThrow(() => writeContentUnit("N2", "rev", 1, entriesFor(1), full));
});

test("manual prune to zero removes every indexed unit", () => {
  const storage = new MemoryStorage();
  writeContentUnit("N2", "rev", 1, entriesFor(1), storage);
  writeContentUnit("N2", "rev", 2, entriesFor(2), storage);
  pruneContentCache(0, storage);
  assert.equal(readContentUnit("N2", "rev", 1, storage), undefined);
  assert.equal(readContentUnit("N2", "rev", 2, storage), undefined);
});
