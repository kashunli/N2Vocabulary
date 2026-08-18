import assert from "node:assert/strict";
import test from "node:test";

import {
  addAudioSequenceStep,
  materializeAudioSequence,
  normalizeAudioSequence,
} from "./audioSequence.mjs";

const entry = {
  word_audio_url: "/audio/word.mp3",
  sentence_audio_url: "/audio/sentence.mp3",
};

test("the default recipe keeps the current word-then-sentence behavior", () => {
  const sequence = normalizeAudioSequence(null);
  assert.deepEqual(sequence.steps.map((step) => step.element), ["word", "sentence"]);
  assert.deepEqual(materializeAudioSequence(sequence, entry).map((step) => step.occurrenceId), ["word-1:0", "sentence-1:0"]);
});

test("a repeated recipe step becomes separate playback occurrences", () => {
  const sequence = normalizeAudioSequence({
    steps: [{id: "sentence-again", element: "sentence", repeatCount: 2, pauseAfterMs: 700}],
  });
  const occurrences = materializeAudioSequence(sequence, entry);
  assert.equal(occurrences.length, 2);
  assert.deepEqual(occurrences.map((step) => step.repeatIndex), [0, 1]);
  assert.deepEqual(occurrences.map((step) => step.occurrenceId), ["sentence-again:0", "sentence-again:1"]);
});

test("the recipe skips unavailable audio", () => {
  const sequence = normalizeAudioSequence({
    steps: [
      {id: "word", element: "word", repeatCount: 1, pauseAfterMs: 500},
      {id: "missing-sentence", element: "sentence", repeatCount: 1, pauseAfterMs: 500},
      {id: "word-again", element: "word", repeatCount: 1, pauseAfterMs: 500},
    ],
  });
  assert.deepEqual(materializeAudioSequence(sequence, {word_audio_url: "/audio/word.mp3"}).map((step) => step.element), ["word", "word"]);
});

test("adding a step preserves stable ids and limits the editor size", () => {
  const steps = [{id: "word-1", element: "word", repeatCount: 1, pauseAfterMs: 500}];
  const next = addAudioSequenceStep(steps, "word");
  assert.deepEqual(next.map((step) => step.id), ["word-1", "word-2"]);
});
