import test from "node:test";
import assert from "node:assert/strict";

import { LANGUAGE_STORAGE_KEY, normalizeLanguage, readStoredLanguage } from "../../language.mjs";

test("language values fail safe to English and accept Chinese mode", () => {
  assert.equal(normalizeLanguage("zh"), "zh");
  assert.equal(normalizeLanguage("en"), "en");
  assert.equal(normalizeLanguage("global"), "en");
  assert.equal(normalizeLanguage(undefined), "en");
});

test("stored language reads the versioned preference", () => {
  const values = new Map([[LANGUAGE_STORAGE_KEY, "zh"]]);
  assert.equal(readStoredLanguage({getItem: key => values.get(key) || null}), "zh");
  assert.equal(readStoredLanguage({getItem: () => "unknown"}), "en");
  assert.equal(readStoredLanguage({getItem: () => { throw new Error("blocked"); }}), "en");
});
