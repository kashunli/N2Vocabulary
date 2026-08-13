import assert from "node:assert/strict";
import test from "node:test";

import {initialDueAt, nextGoodIntervalDays, scheduleReview} from "./reviewScheduler.mjs";

const NOW = "2026-08-13T00:00:00.000Z";

test("new cards start one day after complete playback", () => {
  assert.equal(initialDueAt(NOW), "2026-08-14T00:00:00.000Z");
});

test("again resets and hard preserves the ladder", () => {
  assert.deepEqual(scheduleReview(4, "again", NOW), {
    goodStep: 0,
    dueAt: "2026-08-13T00:10:00.000Z",
    setKnown: false,
    setFlagged: false,
  });
  assert.deepEqual(scheduleReview(4, "hard", NOW), {
    goodStep: 4,
    dueAt: "2026-08-14T00:00:00.000Z",
    setKnown: false,
    setFlagged: true,
  });
});

test("good follows and caps the gentle ladder", () => {
  assert.deepEqual([0, 1, 2, 3, 4, 5, 6].map(nextGoodIntervalDays), [1, 3, 7, 14, 30, 60, 60]);
  assert.equal(scheduleReview(5, "good", NOW).goodStep, 6);
  assert.equal(scheduleReview(6, "good", NOW).dueAt, "2026-10-12T00:00:00.000Z");
});
