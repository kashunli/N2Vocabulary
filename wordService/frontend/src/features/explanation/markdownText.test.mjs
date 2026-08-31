import assert from "node:assert/strict";
import test from "node:test";

import {isDuplicateMarkdownParagraph} from "./markdownText.mjs";

test("recognizes a Markdown-wrapped duplicate translation", () => {
  assert.equal(
    isDuplicateMarkdownParagraph(["**During class, I take notes.**"], "During class, I take notes."),
    true,
  );
});

test("keeps an explanation paragraph that adds context", () => {
  assert.equal(
    isDuplicateMarkdownParagraph(["**During class, I take notes.** This explains the usage."], "During class, I take notes."),
    false,
  );
});

test("can match either bilingual sentence translation", () => {
  assert.equal(
    isDuplicateMarkdownParagraph(["**上课时我记笔记。**"], ["During class, I take notes.", "上课时我记笔记。"]),
    true,
  );
});
