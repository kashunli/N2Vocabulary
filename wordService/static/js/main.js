import { fetchBooks, fetchEntries, fetchStarredSentences, fetchSummary, fetchUnits } from "./api.js";
import { exportFlaggedAudio, moveScopePlayback, replayScopeImmediately, resumeScopePlaybackFromSavedState, seekRailWavebar, stopScopePlayback, toggleScopePlayback, updateScopePlaybackButton } from "./audio.js";
import { configureCards, renderCards, toggleCurrentPlaybackMark } from "./cards.js";
import { closeDetail, configureDetail, openDetail } from "./detail.js";
import { escapeHTML, exampleKey, unitLabel } from "./format.js";
import { configureStarred, renderStarredView } from "./starred.js";
import {
  elements,
  readSavedPlaybackState,
  restoreRailLayoutSettings,
  restoreSavedViewState,
  restorePlaybackSettings,
  restoreRailBlur,
  resetPlaybackSettings,
  restoreScrollPosition,
  savePlaybackSettings,
  saveRailLayoutSettings,
  savePlaybackState,
  saveViewState,
  scheduleScrollSave,
  setPlaybackMode,
  setRailBlur,
  showError,
  state,
  updateAudioExportButton,
  updateFilterPills,
} from "./state.js";

let entriesLoadToken = 0;

function updatePlaybackSettingsUI() {
  const value = state.postSentenceSilenceMs;
  elements.postSentenceSilence.value = String(value);
  elements.postSentenceSilenceValue.textContent = `${value} ms`;
  elements.playbackModeOptions.forEach(option => {
    const selected = option.dataset.playbackMode === state.playbackMode;
    option.classList.toggle("selected", selected);
    option.setAttribute("aria-checked", selected ? "true" : "false");
    option.tabIndex = selected ? 0 : -1;
  });
}

function applyBlurUI() {
  if (!elements.blurButton) return;
  document.body.classList.toggle("is-blurred", state.blurred);
  elements.blurButton.setAttribute("aria-pressed", state.blurred ? "true" : "false");
  elements.blurButton.title = state.blurred
    ? "B: reveal the list and panel"
    : "B: blur the list and panel";
}

function openPlaybackSettings() {  updatePlaybackSettingsUI();
  elements.settingsBackdrop.classList.add("open");
  elements.settingsBackdrop.setAttribute("aria-hidden", "false");
  elements.postSentenceSilence.focus();
}

function closePlaybackSettings() {
  elements.settingsBackdrop.classList.remove("open");
  elements.settingsBackdrop.setAttribute("aria-hidden", "true");
  elements.settingsButton.focus();
}

function railLayoutBounds() {
  const layout = elements.railResizer?.parentElement;
  if (!layout) return null;
  const bounds = layout.getBoundingClientRect();
  return {
    layout,
    min: 220,
    max: Math.max(220, Math.min(620, Math.floor(bounds.width - 430 - 14))),
  };
}

function updateRailWidthUI() {
  const bounds = railLayoutBounds();
  if (!bounds) return;
  state.railListWidthPx = Math.min(bounds.max, Math.max(bounds.min, state.railListWidthPx));
  bounds.layout.style.setProperty("--rail-list-width", `${state.railListWidthPx}px`);
  elements.railResizer.setAttribute("aria-valuenow", String(state.railListWidthPx));
}

function setRailWidthFromPointer(clientX) {
  const bounds = railLayoutBounds();
  if (!bounds) return;
  state.railListWidthPx = Math.min(bounds.max, Math.max(bounds.min, Math.round(clientX - bounds.layout.getBoundingClientRect().left)));
  updateRailWidthUI();
}

function wireRailResizer() {
  if (!elements.railResizer) return;
  updateRailWidthUI();
  let resizing = false;

  const stopResizing = () => {
    if (!resizing) return;
    resizing = false;
    document.body.classList.remove("is-resizing-rail");
    saveRailLayoutSettings();
  };

  elements.railResizer.addEventListener("pointerdown", event => {
    event.preventDefault();
    resizing = true;
    document.body.classList.add("is-resizing-rail");
    elements.railResizer.setPointerCapture?.(event.pointerId);
    setRailWidthFromPointer(event.clientX);
  });
  elements.railResizer.addEventListener("pointermove", event => {
    if (resizing) setRailWidthFromPointer(event.clientX);
  });
  elements.railResizer.addEventListener("pointerup", stopResizing);
  elements.railResizer.addEventListener("pointercancel", stopResizing);
  elements.railResizer.addEventListener("keydown", event => {
    const bounds = railLayoutBounds();
    if (!bounds) return;
    const step = event.shiftKey ? 50 : 20;
    if (event.key === "ArrowLeft") state.railListWidthPx -= step;
    else if (event.key === "ArrowRight") state.railListWidthPx += step;
    else if (event.key === "Home") state.railListWidthPx = bounds.min;
    else if (event.key === "End") state.railListWidthPx = bounds.max;
    else return;
    event.preventDefault();
    updateRailWidthUI();
    saveRailLayoutSettings();
  });
}

function currentBook() {
  return state.books.find(book => book.code === state.selectedBook) || {
    code: state.selectedBook,
    title: `${state.selectedBook} 語彙`,
  };
}

async function loadBooks() {
  const payload = await fetchBooks();
  state.books = payload.items || [];
  if (!state.books.some(book => book.code === state.selectedBook)) {
    state.selectedBook = (state.books[0] && state.books[0].code) || "N2";
  }
  renderBooks();
}

function renderBooks() {
  elements.bookSelect.innerHTML = "";
  state.books.forEach(book => {
    const option = document.createElement("option");
    option.value = book.code;
    option.textContent = `${book.code} - ${book.title}`;
    option.selected = book.code === state.selectedBook;
    elements.bookSelect.appendChild(option);
  });
  const book = currentBook();
  elements.pageTitle.textContent = "スタディウォール";
  document.title = `${book.code} Study Wall`;
}

async function loadSummary() {
  const summary = await fetchSummary();
  const book = currentBook();
  elements.summaryMeta.innerHTML = [
    `<span>${escapeHTML(book.title)}</span>`,
    `<span>${summary.entries} entries</span>`,
    `<span>${summary.units} sections</span>`,
    `<span>${summary.known} known</span>`,
    `<span>${summary.flagged} flagged</span>`,
    `<span>${summary.unmarked} unmarked</span>`,
  ].join("");
}

async function loadUnits() {
  const payload = await fetchUnits();
  state.units = payload.items || [];
  const hasAllUnitSelection = state.selectedUnit === null;
  const savedUnitExists = state.units.some(unit => unit.number === state.selectedUnit);
  state.selectedUnit = hasAllUnitSelection
    ? null
    : (savedUnitExists ? state.selectedUnit : (state.units[0] && state.units[0].number));
  renderUnits();
}

function renderUnits() {
  elements.unitSelect.innerHTML = "";
  elements.unitStrip.innerHTML = "";

  const allOption = document.createElement("option");
  allOption.value = "";
  allOption.textContent = "All sections";
  allOption.selected = state.selectedUnit === null;
  elements.unitSelect.appendChild(allOption);

  const allButton = document.createElement("button");
  allButton.type = "button";
  allButton.className = "unit-tab";
  allButton.textContent = "All";
  allButton.classList.toggle("active", state.selectedUnit === null);
  allButton.title = "Browse words from every section";
  allButton.addEventListener("click", () => selectUnit(null));
  elements.unitStrip.appendChild(allButton);

  state.units.forEach(unit => {
    const option = document.createElement("option");
    option.value = String(unit.number);
    option.textContent = `${unitLabel(unit)} - ${unit.entry_count} words`;
    option.selected = unit.number === state.selectedUnit;
    elements.unitSelect.appendChild(option);

    const button = document.createElement("button");
    button.type = "button";
    button.className = "unit-tab";
    button.textContent = unitLabel(unit);
    button.classList.toggle("active", unit.number === state.selectedUnit);
    button.title = `${unit.title} - ${unit.entry_count} words`;
    button.addEventListener("click", () => selectUnit(unit.number));
    elements.unitStrip.appendChild(button);
  });
}

async function selectUnit(unitNumber) {
  const parsedUnit = Number(unitNumber);
  state.selectedUnit = Number.isFinite(parsedUnit) && parsedUnit > 0 ? parsedUnit : null;
  saveViewState();
  renderUnits();
  await loadEntries();
}

async function loadEntries() {
  if (!state.units.length) return;
  const loadToken = entriesLoadToken + 1;
  entriesLoadToken = loadToken;
  stopScopePlayback({clearSaved: false});
  state.entriesLoading = true;
  updateScopePlaybackButton();
  const params = new URLSearchParams({
    state: state.filterState,
    search: state.search,
  });
  // Omitting `unit` is the public API contract for all-unit listing/filtering.
  if (Number.isFinite(state.selectedUnit) && !state.search) {
    params.set("unit", String(state.selectedUnit));
  }
  try {
    const payload = await fetchEntries(params);
    if (loadToken !== entriesLoadToken) return;
    state.currentEntries = payload.items || [];
    renderCards();
  } finally {
    if (loadToken === entriesLoadToken) {
      state.entriesLoading = false;
      updateScopePlaybackButton();
    }
  }
}

async function loadStarredSentences() {
  const params = new URLSearchParams();
  if (state.starredScope === "unit" && state.selectedUnit) {
    params.set("unit", String(state.selectedUnit));
  }
  const payload = await fetchStarredSentences(params);
  state.starredSentences = payload.items || [];
  if (!state.starredSentences.some(item => exampleKey(item.entry_id, item.position) === state.selectedStarredKey)) {
    const first = state.starredSentences[0];
    state.selectedStarredKey = first ? exampleKey(first.entry_id, first.position) : null;
    saveViewState();
  }
  renderStarredView();
}

async function showCardView() {
  state.view = "cards";
  saveViewState();
  elements.cardView.hidden = false;
  elements.starredView.hidden = true;
  elements.starredViewButton.classList.remove("active");
  elements.starredViewButton.setAttribute("aria-pressed", "false");
  await loadEntries();
  await resumeScopePlaybackFromSavedState(state.currentEntries);
}

async function showStarredView(options = {}) {
  stopScopePlayback();
  state.view = "starred";
  if (options.resetScope) state.starredScope = "all";
  saveViewState();
  elements.cardView.hidden = true;
  elements.starredView.hidden = false;
  elements.starredViewButton.classList.add("active");
  elements.starredViewButton.setAttribute("aria-pressed", "true");
  await loadStarredSentences();
}

function wireControls() {
  elements.bookSelect.addEventListener("change", event => {
    state.selectedBook = (event.target.value || "N2").toUpperCase();
    state.selectedUnit = undefined;
    state.coveredEntryIds.clear();
    state.selectedStarredKey = null;
    saveViewState();
    renderBooks();
    loadSummary()
      .then(loadUnits)
      .then(() => state.view === "starred" ? loadStarredSentences() : loadEntries())
      .catch(showError);
  });
  elements.unitSelect.addEventListener("change", event => {
    selectUnit(event.target.value).then(() => {
      if (state.view === "starred" && state.starredScope === "unit") {
        return loadStarredSentences();
      }
    }).catch(showError);
  });
  elements.search.addEventListener("input", () => {
    state.search = elements.search.value.trim();
    if (state.view !== "cards") {
      showCardView().catch(showError);
      return;
    }
    loadEntries().catch(showError);
  });
  elements.statePills.forEach(pill => {
    pill.addEventListener("click", () => {
      state.filterState = pill.dataset.state || "all";
      updateFilterPills();
      saveViewState();
      showCardView().catch(showError);
    });
  });
  elements.coverAll.addEventListener("click", () => {
    if (state.view !== "cards") {
      showCardView().catch(showError);
      return;
    }
    const shouldCover = state.currentEntries.some(entry => !state.coveredEntryIds.has(entry.entry_id));
    state.currentEntries.forEach(entry => {
      if (shouldCover) {
        state.coveredEntryIds.add(entry.entry_id);
      } else {
        state.coveredEntryIds.delete(entry.entry_id);
      }
    });
    renderCards();
  });
  elements.scopePlayButton.addEventListener("click", () => {
    toggleScopePlayback().catch(showError);
  });
  elements.scopeReplayButton.addEventListener("click", () => replayScopeImmediately().catch(showError));
  elements.scopePreviousButton.addEventListener("click", () => {
    moveScopePlayback(-1).catch(showError);
  });
  elements.scopePauseButton.addEventListener("click", () => {
    toggleScopePlayback().catch(showError);
  });
  elements.scopeNextButton.addEventListener("click", () => {
    moveScopePlayback(1).catch(showError);
  });
  elements.scopeStopButton.addEventListener("click", () => stopScopePlayback({announce: true}));
  if (elements.railWavebarSeek) {
    elements.railWavebarSeek.addEventListener("input", event => {
      seekRailWavebar(Number(event.target.value));
    });
    elements.railWavebarSeek.addEventListener("change", event => {
      seekRailWavebar(Number(event.target.value));
    });
  }
  elements.audioExportButton.addEventListener("click", () => {
    exportFlaggedAudio().catch(showError);
  });
  elements.settingsButton.addEventListener("click", openPlaybackSettings);
  if (elements.blurButton) {
    elements.blurButton.addEventListener("click", () => {
      setRailBlur(!state.blurred);
      applyBlurUI();
    });
  }
  elements.settingsClose.addEventListener("click", closePlaybackSettings);
  elements.settingsBackdrop.addEventListener("click", event => {
    if (event.target === elements.settingsBackdrop) closePlaybackSettings();
  });
  elements.playbackModeOptions.forEach(option => {
    option.addEventListener("click", () => {
      setPlaybackMode(option.dataset.playbackMode);
      updatePlaybackSettingsUI();
    });
  });
  elements.postSentenceSilence.addEventListener("input", event => {
    state.postSentenceSilenceMs = Number(event.target.value);
    savePlaybackSettings();
    updatePlaybackSettingsUI();
  });
  elements.resetPlaybackSettings.addEventListener("click", () => {
    resetPlaybackSettings();
    updatePlaybackSettingsUI();
  });
  wireRailResizer();
  elements.starredViewButton.addEventListener("click", () => {
    if (state.view === "starred") {
      showCardView().catch(showError);
    } else {
      showStarredView({resetScope: true}).catch(showError);
    }
  });
  elements.modalClose.addEventListener("click", closeDetail);
  elements.backdrop.addEventListener("click", event => {
    if (event.target === elements.backdrop) closeDetail();
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && elements.settingsBackdrop.classList.contains("open")) {
      closePlaybackSettings();
      return;
    }
    if (event.key === "Escape" && elements.backdrop.classList.contains("open")) {
      closeDetail();
      return;
    }
    const target = event.target;
    if (target instanceof HTMLElement && target.closest("input, textarea, select, [contenteditable='true']")) {
      return;
    }
    if (event.repeat) return;

    const key = event.key.toLowerCase();
    if (event.key === " " || event.code === "Space") {
      // Study shortcuts own Space and Enter outside text entry, even if a
      // control still has focus from an earlier click.
      event.preventDefault();
      event.stopPropagation();
      toggleScopePlayback().catch(showError);
    } else if (event.key === "Enter") {
      event.preventDefault();
      event.stopPropagation();
      toggleCurrentPlaybackMark("known").catch(showError);
    } else if (event.key === "ArrowRight" || key === "d") {
      event.preventDefault();
      moveScopePlayback(1).catch(showError);
    } else if (event.key === "ArrowLeft" || key === "a") {
      event.preventDefault();
      moveScopePlayback(-1).catch(showError);
    } else if (event.key === "Escape") {
      stopScopePlayback({announce: true});
    } else if (key === "r") {
      replayScopeImmediately().catch(showError);
    } else if (key === "b" && elements.blurButton) {
      setRailBlur(!state.blurred);
      applyBlurUI();
    } else if (key === "f") {
      toggleCurrentPlaybackMark("flagged").catch(showError);
    } else if (key === "k") {
      toggleCurrentPlaybackMark("known").catch(showError);
    }
  }, {capture: true});
  window.addEventListener("scroll", scheduleScrollSave, {passive: true});
  window.addEventListener("beforeunload", () => {
    saveViewState();
    savePlaybackState();
  });
}

function configureModules() {
  // Feature modules receive loader callbacks instead of importing this startup
  // module back, which keeps the ES module graph acyclic and easy to inspect.
  configureCards({loadSummary, loadUnits, loadStarredSentences, openDetail});
  configureDetail({loadEntries, loadSummary, loadUnits});
  configureStarred({loadStarredSentences, renderUnits, openDetail});
}

async function init() {
  restoreSavedViewState();
  restorePlaybackSettings();
  restoreRailLayoutSettings();
  restoreRailBlur();
  updatePlaybackSettingsUI();
  applyBlurUI();
  const previewParams = new URLSearchParams(window.location.search);
  const previewUnit = Number(previewParams.get("preview-unit"));
  if (Number.isFinite(previewUnit) && previewUnit > 0) state.selectedUnit = previewUnit;
  if (["all", "known", "flagged", "unmarked"].includes(previewParams.get("preview-state"))) {
    state.filterState = previewParams.get("preview-state");
  }
  updateFilterPills();
  configureModules();
  wireControls();
  await loadBooks();
  await loadSummary();
  await loadUnits();
  updateAudioExportButton();
  updateScopePlaybackButton();
  if (state.view === "starred") {
    await showStarredView();
  } else {
    await showCardView();
  }
  if (previewParams.has("playback-preview")) {
    window.scrollTo({top: 0, left: 0, behavior: "auto"});
  } else {
    restoreScrollPosition();
  }
}

init().catch(showError);
