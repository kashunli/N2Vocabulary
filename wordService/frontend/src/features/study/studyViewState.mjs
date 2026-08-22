// View state is separate from studyFocus because a learner can change the
// visible filters without changing the word currently being played.
export const STUDY_VIEW_STORAGE_KEY = "n2-word-service:view-state:v1";

const FILTER_STATES = new Set(["all", "review", "known", "flagged", "unmarked"]);

/** @typedef {"all" | "review" | "known" | "flagged" | "unmarked"} FilterState */
/**
 * @typedef {Object} StudyViewState
 * @property {string} [selectedBook]
 * @property {number | null} [selectedUnit]
 * @property {FilterState} [filterState]
 */
/**
 * @typedef {Object} StorageLike
 * @property {(key: string) => string | null} getItem
 * @property {(key: string, value: string) => void} setItem
 */

function isRecord(value) {
  return !!value && typeof value === "object";
}

/** @param {unknown} value @returns {StudyViewState} */
export function normalizeStudyViewState(value) {
  if (!isRecord(value)) return {};

  const raw = value;
  const normalized = {};
  if (typeof raw.selectedBook === "string" && raw.selectedBook.trim()) {
    normalized.selectedBook = raw.selectedBook.trim().toUpperCase();
  }
  if (Object.prototype.hasOwnProperty.call(raw, "selectedUnit")) {
    if (raw.selectedUnit === null) {
      normalized.selectedUnit = null;
    } else {
      const unit = Number(raw.selectedUnit);
      if (Number.isInteger(unit) && unit > 0) normalized.selectedUnit = unit;
    }
  }
  if (FILTER_STATES.has(raw.filterState)) normalized.filterState = raw.filterState;
  return normalized;
}

/** @param {StorageLike} [storage] @returns {StudyViewState} */
export function readStudyViewState(storage = window.localStorage) {
  try {
    const raw = storage.getItem(STUDY_VIEW_STORAGE_KEY);
    return raw ? normalizeStudyViewState(JSON.parse(raw)) : {};
  } catch {
    return {};
  }
}

/** @param {StudyViewState} view @param {StorageLike} [storage] */
export function saveStudyViewState(view, storage = window.localStorage) {
  try {
    storage.setItem(STUDY_VIEW_STORAGE_KEY, JSON.stringify(normalizeStudyViewState(view)));
  } catch {
    // localStorage can be unavailable in privacy mode; the current view still
    // remains usable for this page.
  }
}
