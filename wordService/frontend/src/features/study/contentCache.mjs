export const CONTENT_CACHE_PREFIX = "n2-word-service:content:v2";
export const CONTENT_CACHE_INDEX_KEY = `${CONTENT_CACHE_PREFIX}:index`;
export const CONTENT_CACHE_MAX_UNITS = 32;

function defaultStorage() {
  return globalThis.localStorage;
}

export function contentUnitKey(book, revision, unit) {
  return `${CONTENT_CACHE_PREFIX}:${encodeURIComponent(book)}:${encodeURIComponent(revision)}:${unit}`;
}

/** Read one immutable unit scoped by book revision. */
export function readContentUnit(book, revision, unit, storage = defaultStorage()) {
  try {
    const raw = storage.getItem(contentUnitKey(book, revision, unit));
    if (!raw) return undefined;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : undefined;
  } catch {
    return undefined;
  }
}

/**
 * Persist one unit and retain the most recently used unit payloads. A count
 * limit lets large books reuse nearby sections without one oversized write.
 */
export function writeContentUnit(
  book,
  revision,
  unit,
  entries,
  storage = defaultStorage(),
  now = () => Date.now(),
) {
  if (!Array.isArray(entries)) return;
  const key = contentUnitKey(book, revision, unit);
  const payload = JSON.stringify(entries);
  try {
    storage.setItem(key, payload);
  } catch {
    try {
      pruneContentCache(0, storage);
      storage.setItem(key, payload);
    } catch {
      return;
    }
  }
  try {
    const index = readIndex(storage);
    index[key] = now();
    storage.setItem(CONTENT_CACHE_INDEX_KEY, JSON.stringify(index));
  } catch {
    return;
  }
  pruneContentCache(CONTENT_CACHE_MAX_UNITS, storage);
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

/** Evict every cached unit except the `maxUnits` most recently used. */
export function pruneContentCache(maxUnits, storage = defaultStorage()) {
  const index = readIndex(storage);
  const entries = Object.entries(index).sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0));
  const kept = new Set(entries.slice(0, maxUnits).map(([key]) => key));
  for (const [key] of entries) {
    if (!kept.has(key)) {
      try {
        storage.removeItem(key);
      } catch {
        // The index still drops it so a future prune can retry the removal.
      }
      delete index[key];
    }
  }
  try {
    storage.setItem(CONTENT_CACHE_INDEX_KEY, JSON.stringify(index));
  } catch {
    // Individual unit entries remain usable when the index write fails.
  }
}

/**
 * Load only the selected unit. "All sections" is assembled from cached and
 * missing units, never from one monolithic whole-book entries query.
 */
export async function loadContentScope({
  book,
  revision,
  selectedUnit,
  units,
  readUnit = readContentUnit,
  writeUnit = writeContentUnit,
  fetchUnit,
}) {
  const requestedUnits = selectedUnit === null
    ? units.map((unit) => unit.number)
    : [selectedUnit];
  const entriesByUnit = new Map();
  const missingUnits = [];

  for (const unit of requestedUnits) {
    const cached = readUnit(book, revision, unit);
    if (cached) entriesByUnit.set(unit, cached);
    else missingUnits.push(unit);
  }

  // Four workers avoid both a serial waterfall and a burst of dozens of
  // concurrent SQLite queries when All sections has a cold cache.
  let nextMissingIndex = 0;
  const workerCount = Math.min(4, missingUnits.length);
  await Promise.all(Array.from({length: workerCount}, async () => {
    while (nextMissingIndex < missingUnits.length) {
      const unit = missingUnits[nextMissingIndex++];
      const entries = await fetchUnit(unit);
      writeUnit(book, revision, unit, entries);
      entriesByUnit.set(unit, entries);
    }
  }));

  return requestedUnits.flatMap((unit) => entriesByUnit.get(unit) ?? []);
}
