import { unitLabel } from "./format.js";

export const elements = {
  pageTitle: document.getElementById("page-title"),
  summaryMeta: document.getElementById("summary-meta"),
  bookSelect: document.getElementById("book-select"),
  unitSelect: document.getElementById("unit-select"),
  unitStrip: document.getElementById("unit-strip"),
  search: document.getElementById("search"),
  statePills: Array.from(document.querySelectorAll(".state-pill")),
  coverAll: document.getElementById("cover-all"),
  scopePlayButton: document.getElementById("scope-play-button"),
  playbackDock: document.getElementById("playback-dock"),
  playbackNowLabel: document.getElementById("playback-now-label"),
  playbackNowDetail: document.getElementById("playback-now-detail"),
  scopeReplayButton: document.getElementById("scope-replay-button"),
  scopePreviousButton: document.getElementById("scope-previous-button"),
  scopePauseButton: document.getElementById("scope-pause-button"),
  scopeNextButton: document.getElementById("scope-next-button"),
  scopeStopButton: document.getElementById("scope-stop-button"),
  scopePlaybackCount: document.getElementById("scope-playback-count"),
  starredViewButton: document.getElementById("starred-view-button"),
  audioExportButton: document.getElementById("audio-export-button"),
  counter: document.getElementById("counter"),
  banner: document.getElementById("status-banner"),
  cardView: document.getElementById("card-view"),
  grid: document.getElementById("card-grid"),
  starredView: document.getElementById("starred-view"),
  starredUnitList: document.getElementById("starred-unit-list"),
  starredListPanel: document.getElementById("starred-list-panel"),
  starredTitle: document.getElementById("starred-title"),
  starredSubtitle: document.getElementById("starred-subtitle"),
  starredCount: document.getElementById("starred-count"),
  starredList: document.getElementById("starred-list"),
  starredEmpty: document.getElementById("starred-empty"),
  starredDetail: document.getElementById("starred-detail"),
  template: document.getElementById("card-template"),
  backdrop: document.getElementById("backdrop"),
  modalClose: document.querySelector(".modal-close"),
  modalMeta: document.getElementById("modal-meta"),
  modalTitle: document.getElementById("modal-title"),
  modalMeaning: document.getElementById("modal-meaning"),
  modalSentences: document.getElementById("modal-sentences"),
  modalExplanationWrap: document.getElementById("modal-explanation-wrap"),
  modalExplanation: document.getElementById("modal-explanation"),
};

export const state = {
  books: [],
  selectedBook: "N2",
  units: [],
  selectedUnit: undefined,
  filterState: "all",
  search: "",
  view: "cards",
  starredScope: "all",
  savedScrollY: null,
  scrollSaveTimer: null,
  currentAudio: null,
  currentEntries: [],
  starredSentences: [],
  selectedStarredKey: null,
  detailEntry: null,
  coveredEntryIds: new Set(),
  generatingAudioKeys: new Set(),
  // Scoped playback keeps the current Audio object while paused. Resuming that
  // same object preserves its currentTime instead of restarting the clip.
  scopePlaybackStatus: "idle",
  scopePlaybackPosition: 0,
  scopePlaybackTotal: 0,
  scopePlaybackEntryId: null,
  scopePlaybackPhase: "idle",
  entriesLoading: false,
  exportingAudio: false,
};

const VIEW_STATE_STORAGE_KEY = "n2-word-service:view-state:v1";

function readSavedViewState() {
  try {
    const raw = window.localStorage.getItem(VIEW_STATE_STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (error) {
    console.warn("Could not read saved view state", error);
    return {};
  }
}

export function saveViewState(scrollY) {
  const nextScrollY = Number.isFinite(scrollY)
    ? scrollY
    : (Number.isFinite(state.savedScrollY) ? state.savedScrollY : window.scrollY);
  const payload = {
    selectedUnit: state.selectedUnit,
    selectedBook: state.selectedBook,
    filterState: state.filterState,
    view: state.view,
    starredScope: state.starredScope,
    selectedStarredKey: state.selectedStarredKey,
    scrollY: Math.max(0, Math.round(nextScrollY || 0)),
  };

  try {
    window.localStorage.setItem(VIEW_STATE_STORAGE_KEY, JSON.stringify(payload));
  } catch (error) {
    console.warn("Could not save view state", error);
  }
}

export function restoreSavedViewState() {
  const saved = readSavedViewState();
  if (Object.prototype.hasOwnProperty.call(saved, "selectedUnit") && saved.selectedUnit === null) {
    state.selectedUnit = null;
  } else if (Number.isFinite(saved.selectedUnit)) {
    state.selectedUnit = Number(saved.selectedUnit);
  }
  if (typeof saved.selectedBook === "string" && saved.selectedBook.trim()) {
    state.selectedBook = saved.selectedBook.trim().toUpperCase();
  }
  if (["all", "known", "flagged", "unmarked"].includes(saved.filterState)) {
    state.filterState = saved.filterState;
  }
  if (saved.view === "starred" || saved.view === "cards") {
    state.view = saved.view;
  }
  if (saved.starredScope === "unit" || saved.starredScope === "all") {
    state.starredScope = saved.starredScope;
  }
  if (typeof saved.selectedStarredKey === "string") {
    state.selectedStarredKey = saved.selectedStarredKey;
  }
  if (Number.isFinite(saved.scrollY)) {
    state.savedScrollY = Math.max(0, Number(saved.scrollY));
  }
}

export function scheduleScrollSave() {
  if (state.scrollSaveTimer) window.clearTimeout(state.scrollSaveTimer);
  state.scrollSaveTimer = window.setTimeout(() => {
    state.scrollSaveTimer = null;
    saveViewState();
  }, 150);
}

export function restoreScrollPosition() {
  if (!Number.isFinite(state.savedScrollY)) return;
  const targetY = state.savedScrollY;
  state.savedScrollY = null;

  // Wait until API data has rendered into the document before restoring.
  window.requestAnimationFrame(() => {
    window.requestAnimationFrame(() => {
      window.scrollTo({top: targetY, left: 0, behavior: "auto"});
      saveViewState(targetY);
    });
  });
}

export function updateFilterPills() {
  elements.statePills.forEach(pill => {
    pill.classList.toggle("active", (pill.dataset.state || "all") === state.filterState);
  });
}

export function setBanner(message) {
  if (!message) {
    elements.banner.classList.remove("show");
    elements.banner.textContent = "";
    return;
  }
  elements.banner.textContent = message;
  elements.banner.classList.add("show");
}

export function showError(error) {
  console.error(error);
  setBanner(error.message || String(error));
}

export function updateAudioExportButton() {
  const unit = state.units.find(item => item.number === state.selectedUnit);
  const canExport = Number.isFinite(state.selectedUnit) && !state.exportingAudio;
  elements.audioExportButton.disabled = !canExport;
  elements.audioExportButton.textContent = state.exportingAudio
    ? "exporting..."
    : "export flagged audio";
  elements.audioExportButton.title = unit
    ? `Build ${unitLabel(unit)} flagged-word listening MP3`
    : "Pick one section before exporting flagged audio";
  elements.audioExportButton.setAttribute("aria-busy", state.exportingAudio ? "true" : "false");
}
