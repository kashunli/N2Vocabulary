import assert from "node:assert/strict";
import test from "node:test";

import {
  nativeCueId,
  nativeCueLocation,
  playbackEndAction,
  recordCompletedPhase,
} from "./studyPlaybackState.mjs";

test("native cue ids round-trip and malformed callbacks are rejected", () => {
  assert.equal(nativeCueId(3, 2), "cue:3:2");
  assert.deepEqual(nativeCueLocation("cue:3:2"), {entryIndex: 3, cueIndex: 2});
  assert.equal(nativeCueLocation("cue:-1:2"), null);
  assert.equal(nativeCueLocation("word:3:2"), null);
});

test("a card completes once after its required phases", () => {
  const initial = {itemUuid: "item-1", word: false, sentence: false, cardCompleted: false};
  const word = recordCompletedPhase(initial, "item-1", "word", true);
  assert.equal(word.completesCard, false);
  assert.deepEqual(word.progress, {
    itemUuid: "item-1",
    word: true,
    sentence: false,
    cardCompleted: false,
  });

  const sentence = recordCompletedPhase(word.progress, "item-1", "sentence", true);
  assert.equal(sentence.completesCard, true);
  assert.equal(sentence.progress.cardCompleted, true);

  const replay = recordCompletedPhase(sentence.progress, "item-1", "sentence", true);
  assert.equal(replay.completesCard, false);
});

test("word-only entries complete after their word and a new item resets progress", () => {
  const previous = {itemUuid: "item-1", word: true, sentence: true, cardCompleted: true};
  const result = recordCompletedPhase(previous, "item-2", "word", false);
  assert.equal(result.completesCard, true);
  assert.deepEqual(result.progress, {
    itemUuid: "item-2",
    word: true,
    sentence: false,
    cardCompleted: true,
  });
});

test("end-of-cue decisions preserve paused, single, cue, entry, and completion behavior", () => {
  assert.equal(playbackEndAction({autoAdvance: false, runMode: "consecutive", hasNextCue: true, hasNextEntry: true}), "none");
  assert.equal(playbackEndAction({autoAdvance: true, runMode: "single", hasNextCue: true, hasNextEntry: true}), "stop");
  assert.equal(playbackEndAction({autoAdvance: true, runMode: "consecutive", hasNextCue: true, hasNextEntry: true}), "next-cue");
  assert.equal(playbackEndAction({autoAdvance: true, runMode: "consecutive", hasNextCue: false, hasNextEntry: true}), "next-entry");
  assert.equal(playbackEndAction({autoAdvance: true, runMode: "consecutive", hasNextCue: false, hasNextEntry: false}), "complete-sequence");
});
