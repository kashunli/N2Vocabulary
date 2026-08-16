import assert from "node:assert/strict";
import test from "node:test";

import {
  readStudyViewState,
  saveStudyViewState,
  STUDY_VIEW_STORAGE_KEY,
} from "./studyViewState.mjs";

class MemoryStorage {
  constructor() {
    this.values = new Map();
  }

  getItem(key) {
    return this.values.get(key) ?? null;
  }

  setItem(key, value) {
    this.values.set(key, String(value));
  }
}

test("React view selections round-trip through the shared wall state", () => {
  const storage = new MemoryStorage();
  saveStudyViewState({
    selectedBook: "n2",
    selectedUnit: 7,
    filterState: "known",
  }, storage);

  assert.deepEqual(readStudyViewState(storage), {
    selectedBook: "N2",
    selectedUnit: 7,
    filterState: "known",
  });
});

test("an explicit all-sections selection is preserved", () => {
  const storage = new MemoryStorage();
  storage.setItem(STUDY_VIEW_STORAGE_KEY, JSON.stringify({
    selectedBook: "n2",
    selectedUnit: null,
    filterState: "unmarked",
  }));

  assert.deepEqual(readStudyViewState(storage), {
    selectedBook: "N2",
    selectedUnit: null,
    filterState: "unmarked",
  });
});

test("Review is a shared study-state filter", () => {
  const storage = new MemoryStorage();
  saveStudyViewState({filterState: "review"}, storage);
  assert.deepEqual(readStudyViewState(storage), {filterState: "review"});
});

test("invalid saved selections are ignored instead of poisoning the next view", () => {
  const storage = new MemoryStorage();
  storage.setItem(STUDY_VIEW_STORAGE_KEY, JSON.stringify({
    selectedBook: " ",
    selectedUnit: -3,
    filterState: "not-a-filter",
  }));

  assert.deepEqual(readStudyViewState(storage), {});
});
