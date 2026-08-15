import { exportFlaggedAudio, moveScopePlayback, replayScopeImmediately, stopScopePlayback, toggleScopePlayback } from "./audio.js";
import { renderCards, toggleCurrentPlaybackMark } from "./cards.js";
import { loadEntries, loadSummary, loadUnits, renderBooks, selectUnit, showCardView } from "./catalog.js";
import { closeDetail } from "./detail.js";
import { closePlaybackSettings, openPlaybackSettings, updatePlaybackSettingsUI } from "./playbackSettings.js";
import {
  elements,
  resetPlaybackSettings,
  savePlaybackSettings,
  savePlaybackState,
  saveViewState,
  scheduleScrollSave,
  setPlaybackMode,
  showError,
  state,
  updateFilterPills,
} from "./state.js";

export function wireControls() {
  elements.bookSelect.addEventListener("change", event => {
    state.selectedBook = (event.target.value || "N2").toUpperCase();
    state.selectedUnit = undefined;
    state.reviewSession = undefined;
    state.coveredEntryIds.clear();
    saveViewState();
    renderBooks();
    loadSummary()
      .then(loadUnits)
      .then(loadEntries)
      .catch(showError);
  });
  elements.unitSelect.addEventListener("change", event => {
    selectUnit(event.target.value).catch(showError);
  });
  elements.search.addEventListener("input", () => {
    state.search = elements.search.value.trim();
    state.reviewSession = undefined;
    loadEntries().catch(showError);
  });
  elements.statePills.forEach(pill => {
    pill.addEventListener("click", () => {
      state.filterState = pill.dataset.state || "all";
      if (state.filterState !== "review") state.reviewSession = undefined;
      updateFilterPills();
      saveViewState();
      showCardView().catch(showError);
    });
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
  elements.audioExportButton.addEventListener("click", () => {
    exportFlaggedAudio().catch(showError);
  });
  elements.settingsButton.addEventListener("click", openPlaybackSettings);
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
    // Text-entry controls keep their usual browser behavior instead of
    // trapping the study shortcuts after a click.
    if (target instanceof HTMLElement
      && target.closest("input, textarea, select, [contenteditable='true']")) {
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
