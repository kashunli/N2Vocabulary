export const CONTENT_CACHE_PREFIX = "n2-word-service:content:v1";
export const CONTENT_CACHE_INDEX_KEY = `${CONTENT_CACHE_PREFIX}:index`;
export const CONTENT_CACHE_MAX_BOOKS = 3;

function defaultStorage() {
  return globalThis.localStorage;
}

export function contentKey(book) {
  return `${CONTENT_CACHE_PREFIX}:${book}`;
}

/**
 * Read one book's cached content, or undefined when missing/malformed.
 * The stored shape is {revision, summary, units, allEntries}; the caller
 * validates `revision` against a fresh server summary before trusting it.
 */
export function readContentBook(book, storage = defaultStorage()) {
  try {
    const raw = storage.getItem(contentKey(book));
    if (!raw) return undefined;
    const parsed = JSON.parse(raw);
    if (
      !parsed
      || typeof parsed !== "object"
      || typeof parsed.revision !== "string"
      || !parsed.summary
      || !Array.isArray(parsed.units)
      || !Array.isArray(parsed.allEntries)
    ) {
      return undefined;
    }
    return {
      revision: parsed.revision,
      summary: parsed.summary,
      units: parsed.units,
      allEntries: parsed.allEntries,
    };
  } catch {
    return undefined;
  }
}

/**
 * Persist one book's content and keep at most CONTENT_CACHE_MAX_BOOKS books.
 * Storage is a best-effort cache: a quota failure drops the other cached books
 * and retries once, then gives up silently so the app just refetches.
 */
export function writeContentBook(book, content, storage = defaultStorage(), now = () => Date.now()) {
  const payload = JSON.stringify(content);
  try {
    storage.setItem(contentKey(book), payload);
  } catch {
    try {
      pruneContentCache(0, storage);
      storage.setItem(contentKey(book), payload);
    } catch {
      return;
    }
  }
  try {
    const index = readIndex(storage);
    index[book] = now();
    storage.setItem(CONTENT_CACHE_INDEX_KEY, JSON.stringify(index));
  } catch {
    return;
  }
  pruneContentCache(CONTENT_CACHE_MAX_BOOKS, storage);
}

function readIndex(storage) {
  try {
    const raw = storage.getItem(CONTENT_CACHE_INDEX_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

/** Evict every cached book except the `maxBooks` most recently used. */
export function pruneContentCache(maxBooks, storage = defaultStorage()) {
  const index = readIndex(storage);
  const entries = Object.entries(index).sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0));
  const kept = new Set(entries.slice(0, maxBooks).map(([book]) => book));
  for (const [book] of entries) {
    if (!kept.has(book)) {
      try {
        storage.removeItem(contentKey(book));
      } catch {
        // Ignore; the index still drops it so a future prune retries removal.
      }
      delete index[book];
    }
  }
  try {
    storage.setItem(CONTENT_CACHE_INDEX_KEY, JSON.stringify(index));
  } catch {
    // Ignore; per-book entries are still valid.
  }
}
