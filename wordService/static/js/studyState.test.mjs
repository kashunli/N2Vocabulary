import assert from "node:assert/strict";
import test from "node:test";

class MemoryStorage {
  constructor() { this.values = new Map(); }
  getItem(key) { return this.values.get(key) ?? null; }
  setItem(key, value) { this.values.set(key, String(value)); }
}

const storage = new MemoryStorage();
global.window = {localStorage: storage};

const {
  completeStudyReview,
  nextReviewDueAt,
  recordStudyCompleted,
  studyMark,
} = await import("./studyState.js");

test("Classic study state schedules a normal card once and advances a due review once", async () => {
  const entry = {item_uuid: "classic-card", book_code: "N2", source_index: 7};
  const first = await recordStudyCompleted(entry);
  assert.equal(first.review_level, 0);
  const replayed = await recordStudyCompleted({...entry, book_code: "GWB_N2"});
  assert.equal(replayed.due_at, first.due_at);

  const snapshot = JSON.parse(storage.getItem("n2-word-service:study-state:v1"));
  snapshot.cards[entry.item_uuid].due_at = "2020-01-01T00:00:00.000Z";
  storage.setItem("n2-word-service:study-state:v1", JSON.stringify(snapshot));
  const completed = await completeStudyReview(entry, "2020-01-01T00:00:00.000Z");
  assert.equal(completed.completed, true);
  assert.equal(completed.card.review_level, 1);
  assert.equal((await completeStudyReview(entry, "2020-01-01T00:00:00.000Z")).completed, false);
  assert.equal(studyMark(entry.item_uuid).review_level, 1);
});

test("Classic interval calculation doubles and validates bounds", () => {
  assert.equal(nextReviewDueAt("2026-08-13T00:00:00.000Z", 0), "2026-08-14T00:00:00.000Z");
  assert.equal(nextReviewDueAt("2026-08-13T00:00:00.000Z", 5), "2026-09-14T00:00:00.000Z");
  assert.throws(() => nextReviewDueAt("2026-08-13T00:00:00.000Z", 63));
});
