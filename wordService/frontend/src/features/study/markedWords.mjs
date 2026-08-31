export const MARKED_WORDS_FILE_FORMAT = "n2-word-service-marked-words";
export const MARKED_WORDS_FILE_VERSION = 1;
export const MAX_MARKED_WORDS = 10000;

const MARKED_STATUSES = new Set(["known", "flagged"]);

function isRecord(value) {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function invalidFile(message) {
  return new Error(`Invalid marked words file: ${message}`);
}

/**
 * Build the small, portable part of study state. Review scheduling and audio
 * history intentionally stay out of this file: importing marks must not
 * overwrite unrelated progress on the destination device or account.
 */
export function createMarkedWordsExport(snapshot, entries = [], exportedAt = () => new Date().toISOString()) {
  const entriesByUuid = new Map(entries.map((entry) => [entry.item_uuid, entry]));
  const items = Object.values(snapshot.cards || {})
    .filter((card) => MARKED_STATUSES.has(card.status))
    .sort((left, right) => left.item_uuid.localeCompare(right.item_uuid))
    .map((card) => {
      const entry = entriesByUuid.get(card.item_uuid);
      return {
        item_uuid: card.item_uuid,
        status: card.status,
        ...(entry ? {
          word: entry.kanji,
          reading: entry.reading,
          book_code: entry.book_code,
        } : {}),
      };
    });

  return {
    format: MARKED_WORDS_FILE_FORMAT,
    version: MARKED_WORDS_FILE_VERSION,
    exported_at: exportedAt(),
    items,
  };
}
/**
 * Validate and reduce an imported file to the fields that can change study
 * state. Display metadata is accepted for human-readable exports but never
 * trusted as an identifier; item_uuid is the canonical content key.
 */
export function parseMarkedWordsExport(value) {
  if (!isRecord(value) || value.format !== MARKED_WORDS_FILE_FORMAT) {
    throw invalidFile("unrecognized format");
  }
  if (value.version !== MARKED_WORDS_FILE_VERSION) {
    throw invalidFile("unsupported version");
  }
  if (!Array.isArray(value.items)) {
    throw invalidFile("items must be an array");
  }
  if (value.items.length > MAX_MARKED_WORDS) {
    throw invalidFile(`at most ${MAX_MARKED_WORDS} items are allowed`);
  }

  const seen = new Set();
  const items = value.items.map((candidate, index) => {
    if (!isRecord(candidate)) throw invalidFile(`item ${index + 1} must be an object`);
    const itemUuid = typeof candidate.item_uuid === "string" ? candidate.item_uuid.trim() : "";
    if (!itemUuid || itemUuid.length > 200) {
      throw invalidFile(`item ${index + 1} has an invalid item UUID`);
    }
    if (seen.has(itemUuid)) {
      throw invalidFile(`item ${index + 1} duplicates an earlier item UUID`);
    }
    seen.add(itemUuid);
    if (!MARKED_STATUSES.has(candidate.status)) {
      throw invalidFile(`item ${index + 1} must be known or flagged`);
    }
    return {item_uuid: itemUuid, status: candidate.status};
  });

  return {
    format: MARKED_WORDS_FILE_FORMAT,
    version: MARKED_WORDS_FILE_VERSION,
    items,
  };
}
