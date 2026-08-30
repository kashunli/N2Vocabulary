/**
 * Compare rendered Markdown text without treating emphasis/code markers as
 * learner-visible content. This lets the card remove a repeated translation
 * while preserving any explanation paragraph that adds real context.
 */
export function normalizeMarkdownText(value) {
  return value.replace(/[`*_]/g, "").replace(/\s+/g, " ").trim().toLowerCase();
}

export function isDuplicateMarkdownParagraph(lines, translation) {
  return Boolean(translation?.trim())
    && normalizeMarkdownText(lines.join(" ")) === normalizeMarkdownText(translation);
}
