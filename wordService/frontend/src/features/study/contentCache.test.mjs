import assert from "node:assert/strict";
import test from "node:test";

import {
  CONTENT_CACHE_MAX_BOOKS,
  CONTENT_CACHE_PREFIX,
  contentKey,
  pruneContentCache,
  readContentBook,
  writeContentBook,
} from "./contentCache.mjs";

class MemoryStorage {
  constructor() { this.values = new Map(); }
  get length() { return this.values.size; }
  key(index) { return [...this.values.keys()][index] ?? null; }
  getItem(key) { return this.values.get(key) ?? null; }
  setItem(key, value) { this.values.set(key, String(value)); }
  removeItem(key) { this.values.delete(key); }
}

function bookContent(revision, entries = 2) {
  return {
    revision,
    summary: {entries, units: 1, known: 0, flagged: 0, unmarked: entries, content_revision: revision},
    units: [{number: 1, header: "H", title: "T", entry_count: entries}],
    allEntries: Array.from({length: entries}, (_, index) => ({entry_id: index, item_uuid: `u${index}`})),
  };
}

test("write then read returns the same content", () => {
  const storage = new MemoryStorage();
  const content = bookContent("rev-1");
  writeContentBook("N2", content, storage, () => 1);
  assert.deepEqual(readContentBook("N2", storage), content);
  assert.ok(storage.getItem(contentKey("N2")));
});

test("read returns undefined when the book was never cached", () => {
  const storage = new MemoryStorage();
  assert.equal(readContentBook("N1", storage), undefined);
});

test("read returns undefined for malformed payloads", () => {
  const storage = new MemoryStorage();
  storage.setItem(contentKey("N2"), "not json");
  assert.equal(readContentBook("N2", storage), undefined);
  storage.setItem(contentKey("N2"), JSON.stringify({revision: 7, summary: {}, units: [], allEntries: []}));
  assert.equal(readContentBook("N2", storage), undefined);
  storage.setItem(contentKey("N2"), JSON.stringify({revision: "r", units: [], allEntries: []}));
  assert.equal(readContentBook("N2", storage), undefined);
});

test("prune keeps only the most recently used books", () => {
  const storage = new MemoryStorage();
  writeContentBook("A", bookContent("a"), storage, () => 1);
  writeContentBook("B", bookContent("b"), storage, () => 2);
  writeContentBook("C", bookContent("c"), storage, () => 3);
  writeContentBook("D", bookContent("d"), storage, () => 4);
  assert.equal(readContentBook("A", storage), undefined);
  assert.ok(readContentBook("B", storage));
  assert.ok(readContentBook("C", storage));
  assert.ok(readContentBook("D", storage));
  assert.ok(storage.values.size <= CONTENT_CACHE_MAX_BOOKS + 1); // content keys + index
});

test("touching a cached book makes it recent again", () => {
  const storage = new MemoryStorage();
  writeContentBook("A", bookContent("a"), storage, () => 1);
  writeContentBook("B", bookContent("b"), storage, () => 2);
  writeContentBook("A", bookContent("a-v2"), storage, () => 3);
  writeContentBook("C", bookContent("c"), storage, () => 4);
  writeContentBook("D", bookContent("d"), storage, () => 5);
  // A is recent again and survives; B was never re-touched and falls off.
  assert.ok(readContentBook("A", storage));
  assert.ok(readContentBook("C", storage));
  assert.ok(readContentBook("D", storage));
  assert.equal(readContentBook("B", storage), undefined);
});

test("quota failure does not throw and leaves the cache usable", () => {
  const storage = new MemoryStorage();
  writeContentBook("A", bookContent("a", 100), storage, () => 1);
  // Pretend the origin is full: fail every setItem after the first book.
  const full = new MemoryStorage();
  full.setItem = () => { throw new Error("quota"); };
  assert.doesNotThrow(() => writeContentBook("B", bookContent("b"), full, () => 2));
});

test("manual prune to zero removes every book", () => {
  const storage = new MemoryStorage();
  writeContentBook("A", bookContent("a"), storage, () => 1);
  writeContentBook("B", bookContent("b"), storage, () => 2);
  pruneContentCache(0, storage);
  assert.equal(readContentBook("A", storage), undefined);
  assert.equal(readContentBook("B", storage), undefined);
});

test("cache keys are scoped to the v1 prefix", () => {
  assert.ok(contentKey("N2").startsWith(`${CONTENT_CACHE_PREFIX}:`));
});
