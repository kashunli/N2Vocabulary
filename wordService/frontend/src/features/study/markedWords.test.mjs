import assert from "node:assert/strict";
import test from "node:test";

import {
  createMarkedWordsExport,
  MARKED_WORDS_FILE_FORMAT,
  MARKED_WORDS_FILE_VERSION,
  parseMarkedWordsExport,
} from "./markedWords.mjs";

test("export contains only marked statuses and keeps readable entry metadata", () => {
  const payload = createMarkedWordsExport(
    {
      cards: {
        z: {item_uuid: "z", status: "flagged"},
        unmarked: {item_uuid: "unmarked", status: "unmarked"},
        a: {item_uuid: "a", status: "known"},
      },
    },
    [{item_uuid: "a", kanji: "人生", reading: "じんせい", book_code: "N2"}],
    () => "2026-08-31T00:00:00.000Z",
  );

  assert.deepEqual(payload, {
    format: MARKED_WORDS_FILE_FORMAT,
    version: MARKED_WORDS_FILE_VERSION,
    exported_at: "2026-08-31T00:00:00.000Z",
    items: [
      {item_uuid: "a", status: "known", word: "人生", reading: "じんせい", book_code: "N2"},
      {item_uuid: "z", status: "flagged"},
    ],
  });
});

test("import validation reduces metadata and trims identifiers", () => {
  assert.deepEqual(
    parseMarkedWordsExport({
      format: MARKED_WORDS_FILE_FORMAT,
      version: MARKED_WORDS_FILE_VERSION,
      exported_at: "not used",
      items: [{item_uuid: "  item-1 ", status: "known", word: "ignored"}],
    }),
    {
      format: MARKED_WORDS_FILE_FORMAT,
      version: MARKED_WORDS_FILE_VERSION,
      items: [{item_uuid: "item-1", status: "known"}],
    },
  );
});

test("import validation rejects unsupported, unmarked, and duplicate data", () => {
  const base = {format: MARKED_WORDS_FILE_FORMAT, version: MARKED_WORDS_FILE_VERSION};
  assert.throws(() => parseMarkedWordsExport({...base, version: 2, items: []}), /unsupported version/);
  assert.throws(() => parseMarkedWordsExport({...base, items: [{item_uuid: "item", status: "unmarked"}]}), /known or flagged/);
  assert.throws(() => parseMarkedWordsExport({...base, items: [
    {item_uuid: "item", status: "known"},
    {item_uuid: "item", status: "flagged"},
  ]}), /duplicates/);
});
