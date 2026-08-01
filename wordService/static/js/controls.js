import { exportFlaggedAudio, moveScopePlayback, replayScopeImmediately, seekRailWavebar, stopScopePlayback, toggleScopePlayback } from "./audio.js";
import { renderCards, toggleCurrentPlaybackMark } from "./cards.js";
import { loadEntries, loadStarredSentences, loadSummary, loadUnits, renderBooks, selectUnit, showCardView, showStarredView } from "./catalog.js";
import { closeDetail } from "./detail.js";
import { applyBlurUI, closePlaybackSettings, openPlaybackSettings, updatePlaybackSettingsUI } from "./playbackSettings.js";
import { wireRailResizer } from "./railLayout.js";
import {
  elements,
  resetPlaybackSettings,
  savePlaybackSettings,
  savePlaybackState,
  saveViewState,
  scheduleScrollSave,
  setPlaybackMode,
  setRailBlur,
  showError,
  state,
  updateFilterPills,
} from "./state.js";

export function wireControls() {
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
    // The waveform slider remains a normal native range control for mouse
    // and touch seeking, but it must not trap the study shortcuts after a
    // click. Other text-entry controls still keep their usual behavior.
    if (target instanceof HTMLElement
      && target !== elements.railWavebarSeek
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
