import { configureCards } from "./cards.js";
import { updateScopePlaybackButton } from "./audio.js";
import { loadBooks, loadEntries, loadSummary, loadUnits, showCardView } from "./catalog.js";
import { configureDetail, openDetail } from "./detail.js";
import { wireControls } from "./controls.js";
import { updatePlaybackSettingsUI } from "./playbackSettings.js";
import { fetchLegacyMarkSeed } from "./api.js";
import { initializeStudyState, seedLegacyStudyMarks } from "./studyState.js";
import {
  restoreSavedViewState,
  restoreSavedStudyFocus,
  restorePlaybackSettings,
  restoreScrollPosition,
  showError,
  state,
  updateAudioExportButton,
  updateFilterPills,
} from "./state.js";

function configureModules() {
  // Feature modules receive loader callbacks instead of importing this startup
  // module back, which keeps the ES module graph acyclic and easy to inspect.
  configureCards({loadSummary, loadUnits, openDetail});
  configureDetail({loadEntries, loadSummary, loadUnits});
}

async function init() {
  restoreSavedViewState();
  restoreSavedStudyFocus();
  restorePlaybackSettings();
  updatePlaybackSettingsUI();
  const previewParams = new URLSearchParams(window.location.search);
  const previewUnit = Number(previewParams.get("preview-unit"));
  if (Number.isFinite(previewUnit) && previewUnit > 0) state.selectedUnit = previewUnit;
  if (["all", "review", "known", "flagged", "unmarked"].includes(previewParams.get("preview-state"))) {
    state.filterState = previewParams.get("preview-state");
  }
  updateFilterPills();
  configureModules();
  wireControls();
  const accountActive = await initializeStudyState();
  if (!accountActive) seedLegacyStudyMarks((await fetchLegacyMarkSeed()).items || []);
  await loadBooks();
  await loadUnits();
  await loadSummary();
  updateAudioExportButton();
  updateScopePlaybackButton();
  await showCardView();
  if (previewParams.has("playback-preview")) {
    window.scrollTo({top: 0, left: 0, behavior: "auto"});
  } else {
    restoreScrollPosition();
  }
}

init().catch(showError);
