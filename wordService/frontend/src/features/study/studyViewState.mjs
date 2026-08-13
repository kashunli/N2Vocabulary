// Keep this payload contract compatible with the Classic wall's state.js.
// View state is separate from studyFocus because a learner can change the
// visible filters without changing the word currently being played.
export const STUDY_VIEW_STORAGE_KEY = "n2-word-service:view-state:v1";

const FILTER_STATES = new Set(["all", "known", "flagged", "unmarked"]);
const VIEWS = new Set(["cards", "starred"]);

function isRecord(value) {
  return !!value && typeof value === "object";
}

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
  if (typeof raw.search === "string") normalized.search = raw.search;
  if (VIEWS.has(raw.view)) normalized.view = raw.view;
  if (raw.starredScope === "all" || raw.starredScope === "unit") normalized.starredScope = raw.starredScope;
  if (typeof raw.selectedStarredKey === "string" && raw.selectedStarredKey) {
    normalized.selectedStarredKey = raw.selectedStarredKey;
  }
  return normalized;
}

export function readStudyViewState(storage = window.localStorage) {
  try {
    const raw = storage.getItem(STUDY_VIEW_STORAGE_KEY);
    return raw ? normalizeStudyViewState(JSON.parse(raw)) : {};
  } catch {
    return {};
  }
}

export function saveStudyViewState(view, storage = window.localStorage) {
  try {
    storage.setItem(STUDY_VIEW_STORAGE_KEY, JSON.stringify(normalizeStudyViewState(view)));
  } catch {
    // localStorage can be unavailable in privacy mode; the current view still
    // remains usable for this page.
  }
}
