import { unitLabel } from "./format.js";
import { readStudyFocus, saveStudyFocus } from "./studyFocus.js";

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
  audioExportButton: document.getElementById("audio-export-button"),
  counter: document.getElementById("counter"),
  banner: document.getElementById("status-banner"),
  cardView: document.getElementById("card-view"),
  grid: document.getElementById("card-grid"),
  template: document.getElementById("card-template"),
  backdrop: document.getElementById("backdrop"),
  modalClose: document.querySelector(".modal-close"),
  modalMeta: document.getElementById("modal-meta"),
  modalTitle: document.getElementById("modal-title"),
  modalMeaning: document.getElementById("modal-meaning"),
  modalSentences: document.getElementById("modal-sentences"),
  modalSourceWrap: document.getElementById("modal-source-wrap"),
  modalSource: document.getElementById("modal-source"),
  modalExplanationWrap: document.getElementById("modal-explanation-wrap"),
  modalExplanation: document.getElementById("modal-explanation"),
  settingsButton: document.getElementById("settings-button"),
  settingsBackdrop: document.getElementById("settings-backdrop"),
  settingsClose: document.getElementById("settings-close"),
  playbackModeOptions: Array.from(document.querySelectorAll(".setting-option[data-playback-mode]")),
  postSentenceSilence: document.getElementById("post-sentence-silence"),
  postSentenceSilenceValue: document.getElementById("post-sentence-silence-value"),
  resetPlaybackSettings: document.getElementById("reset-playback-settings"),
};

export const state = {
  books: [],
  selectedBook: "N2",
  units: [],
  selectedUnit: undefined,
  filterState: "all",
  reviewSession: undefined,
  search: "",
  focusedEntryId: null,
  focusedPhase: "word",
  savedScrollY: null,
  scrollSaveTimer: null,
  currentAudio: null,
  currentEntries: [],
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
  postSentenceSilenceMs: 500,
  playbackMode: "both",
  entriesLoading: false,
  exportingAudio: false,
};

const VIEW_STATE_STORAGE_KEY = "n2-word-service:view-state:v1";
const PLAYBACK_STATE_KEY = "n2-word-service:playback-state:v1";
const PLAYBACK_SETTINGS_KEY = "n2-word-service:playback-settings:v1";
const DEFAULT_POST_SENTENCE_SILENCE_MS = 500;
const PLAYBACK_MODES = ["both", "words", "sentences"];

function normalizePlaybackMode(value) {
  return PLAYBACK_MODES.includes(value) ? value : "both";
}

export function restorePlaybackSettings() {
  try {
    const raw = window.localStorage.getItem(PLAYBACK_SETTINGS_KEY);
    const saved = raw ? JSON.parse(raw) : {};
    const value = Number(saved.postSentenceSilenceMs);
    if (Number.isFinite(value)) {
      state.postSentenceSilenceMs = Math.min(3000, Math.max(0, Math.round(value / 100) * 100));
    }
    state.playbackMode = normalizePlaybackMode(saved.playbackMode);
  } catch (error) {
    console.warn("Could not read playback settings", error);
  }
}

export function savePlaybackSettings() {
  try {
    window.localStorage.setItem(PLAYBACK_SETTINGS_KEY, JSON.stringify({
      postSentenceSilenceMs: state.postSentenceSilenceMs,
      playbackMode: state.playbackMode,
    }));
  } catch (error) {
    console.warn("Could not save playback settings", error);
  }
}

export function resetPlaybackSettings() {
  state.postSentenceSilenceMs = DEFAULT_POST_SENTENCE_SILENCE_MS;
  state.playbackMode = "both";
  savePlaybackSettings();
}

export function setPlaybackMode(mode) {
  state.playbackMode = normalizePlaybackMode(mode);
  savePlaybackSettings();
}

export function savePlaybackState() {
  if (state.scopePlaybackStatus === "idle") {
    clearSavedPlaybackState();
    return;
  }
  const payload = {
    scopePlaybackStatus: state.scopePlaybackStatus,
    scopePlaybackPosition: state.scopePlaybackPosition,
    scopePlaybackTotal: state.scopePlaybackTotal,
    scopePlaybackEntryId: state.scopePlaybackEntryId,
    scopePlaybackPhase: state.scopePlaybackPhase,
    audioCurrentTime: state.currentAudio ? state.currentAudio.currentTime : null,
  };
  try {
    window.localStorage.setItem(PLAYBACK_STATE_KEY, JSON.stringify(payload));
  } catch (error) {
    console.warn("Could not save playback state", error);
  }
}

export function readSavedPlaybackState() {
  try {
    const raw = window.localStorage.getItem(PLAYBACK_STATE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function clearSavedPlaybackState() {
  try {
    window.localStorage.removeItem(PLAYBACK_STATE_KEY);
  } catch (error) {
    console.warn("Could not clear playback state", error);
  }
}

export function restoreSavedStudyFocus() {
  const saved = readStudyFocus();
  if (!saved) return;
  state.focusedEntryId = saved.entryId;
  state.focusedPhase = saved.phase;
  // The focus record carries the book so changing walls does not silently
  // reopen a different vocabulary set from the one the learner last read.
  state.selectedBook = saved.bookCode;
  // If the classic wall had a section filter that would hide the saved card,
  // follow the focus record into that section. An explicit all-sections choice
  // (`null`) remains all-sections so the card is still shown in context.
  if (Number.isFinite(saved.unitNumber)
    && (state.selectedUnit === undefined
      || (Number.isFinite(state.selectedUnit) && state.selectedUnit !== saved.unitNumber))) {
    state.selectedUnit = saved.unitNumber;
  }
}

export function applyStudyFocusVisual() {
  elements.grid.querySelectorAll(".card.study-focus").forEach(card => {
    card.classList.remove("study-focus", "study-focus-word", "study-focus-sentence");
    delete card.dataset.studyFocusPhase;
  });
  if (!Number.isFinite(state.focusedEntryId)) return;
  const card = elements.grid.querySelector(`.card[data-id="${state.focusedEntryId}"]`);
  if (!card) return;
  card.classList.add("study-focus", `study-focus-${state.focusedPhase}`);
  card.dataset.studyFocusPhase = state.focusedPhase;
}

export function focusStudyEntry(entryId, phase = "word") {
  const entry = state.currentEntries.find(item => item.entry_id === Number(entryId));
  if (!entry) return false;
  const nextPhase = phase === "sentence" && entry.sentence_audio_url ? "sentence" : "word";
  state.focusedEntryId = entry.entry_id;
  state.focusedPhase = nextPhase;
  applyStudyFocusVisual();
  saveStudyFocus({
    bookCode: entry.book_code || state.selectedBook,
    entryId: entry.entry_id,
    phase: nextPhase,
    unitNumber: entry.unit?.number,
  });
  return true;
}

export function focusStudyEntryFromViewport() {
  if (state.entriesLoading || !state.currentEntries.length) return;
  const cards = Array.from(elements.grid.querySelectorAll(".card"));
  if (!cards.length) return;
  const viewportCenter = window.innerHeight / 2;
  let closestCard = null;
  let closestDistance = Number.POSITIVE_INFINITY;
  cards.forEach(card => {
    const bounds = card.getBoundingClientRect();
    const distance = Math.abs((bounds.top + bounds.bottom) / 2 - viewportCenter);
    if (distance < closestDistance) {
      closestCard = card;
      closestDistance = distance;
    }
  });
  if (!closestCard) return;
  const entryId = Number(closestCard.dataset.id);
  const phase = entryId === state.focusedEntryId ? state.focusedPhase : "word";
  if (entryId === state.focusedEntryId && phase === state.focusedPhase) {
    applyStudyFocusVisual();
    return;
  }
  focusStudyEntry(entryId, phase);
}

export function restoreStudyFocusPosition() {
  const saved = readStudyFocus();
  if (!saved || saved.bookCode !== state.selectedBook) return false;
  state.focusedEntryId = saved.entryId;
  state.focusedPhase = saved.phase;
  applyStudyFocusVisual();
  const card = elements.grid.querySelector(`.card[data-id="${saved.entryId}"]`);
  if (!card) return false;
  window.requestAnimationFrame(() => {
    window.requestAnimationFrame(() => {
      card.scrollIntoView({behavior: "auto", block: "center"});
      applyStudyFocusVisual();
    });
  });
  return true;
}

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
  if (["all", "review", "known", "flagged", "unmarked"].includes(saved.filterState)) {
    state.filterState = saved.filterState;
  }
  if (Number.isFinite(saved.scrollY)) {
    state.savedScrollY = Math.max(0, Number(saved.scrollY));
  }
}

export function scheduleScrollSave() {
  if (state.scrollSaveTimer) window.clearTimeout(state.scrollSaveTimer);
  state.scrollSaveTimer = window.setTimeout(() => {
    state.scrollSaveTimer = null;
    focusStudyEntryFromViewport();
    saveViewState();
  }, 150);
}

export function restoreScrollPosition() {
  if (restoreStudyFocusPosition()) {
    state.savedScrollY = null;
    return;
  }
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
