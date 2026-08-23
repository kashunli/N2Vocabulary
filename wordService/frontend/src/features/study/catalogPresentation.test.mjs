import assert from "node:assert/strict";
import test from "node:test";

import { deriveCatalogPresentation } from "./catalogPresentation.mjs";

const markStatusOf = (mark) => mark?.status ?? "unmarked";
const isReviewDue = (dueAt) => dueAt === "due";

const n2Summary = {
  entries: 4,
  units: 2,
  known: 0,
  flagged: 0,
  review: 0,
  unmarked: 4,
  content_revision: "n2-r1",
};
const n2Units = [
  {number: 1, header: "1", title: "One", entry_count: 2},
  {number: 2, header: "2", title: "Two", entry_count: 2},
];
const entries = [
  {item_uuid: "n2-1", book_code: "N2", unit: {number: 1}},
  {item_uuid: "n2-2", book_code: "N2", unit: {number: 1}},
  {item_uuid: "n2-3", book_code: "N2", unit: {number: 2}},
  {item_uuid: "n2-4", book_code: "N2", unit: {number: 2}},
  {item_uuid: "n1-1", book_code: "N1", unit: {number: 1}},
];

function present(overrides = {}) {
  return deriveCatalogPresentation({
    bookSummary: n2Summary,
    sourceUnits: n2Units,
    allEntries: entries,
    selectedBook: "N2",
    selectedUnit: null,
    cards: {},
    markStatusOf,
    isReviewDue,
    ...overrides,
  });
}

test("all sections restores the original book unit count after one section", () => {
  const all = present();
  const oneSection = present({selectedUnit: 1});
  const allAgain = present();

  assert.equal(all.summary.units, 2);
  assert.equal(oneSection.summary.units, 1);
  assert.equal(allAgain.summary.units, 2);
  assert.equal(n2Summary.units, 2);
});

test("book presentation never includes another book's entries", () => {
  const presentation = present({
    bookSummary: {...n2Summary, entries: 1, units: 1, content_revision: "n1-r1"},
    sourceUnits: [{number: 1, header: "1", title: "N1", entry_count: 1}],
    selectedBook: "N1",
  });

  assert.equal(presentation.summary.entries, 1);
  assert.equal(presentation.summary.units, 1);
  assert.equal(presentation.units[0].entry_count, 1);
});

test("study-state counts update without mutating the server book summary", () => {
  const presentation = present({
    cards: {
      "n2-1": {status: "known"},
      "n2-2": {status: "flagged", due_at: "due"},
    },
  });

  assert.deepEqual(
    {
      known: presentation.summary.known,
      flagged: presentation.summary.flagged,
      review: presentation.summary.review,
      unmarked: presentation.summary.unmarked,
    },
    {known: 1, flagged: 1, review: 1, unmarked: 2},
  );
  assert.deepEqual(n2Summary, {
    entries: 4,
    units: 2,
    known: 0,
    flagged: 0,
    review: 0,
    unmarked: 4,
    content_revision: "n2-r1",
  });
});
