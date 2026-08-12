import { configureCards } from "./cards.js";
import { updateScopePlaybackButton } from "./audio.js";
import { loadBooks, loadEntries, loadStarredSentences, loadSummary, loadUnits, renderUnits, showCardView, showStarredView } from "./catalog.js";
import { configureDetail, openDetail } from "./detail.js";
import { wireControls } from "./controls.js";
import { configureStarred } from "./starred.js";
import { updatePlaybackSettingsUI } from "./playbackSettings.js";
import {
  restoreSavedViewState,
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
  configureCards({loadSummary, loadUnits, loadStarredSentences, openDetail});
  configureDetail({loadEntries, loadSummary, loadUnits});
  configureStarred({loadStarredSentences, renderUnits, openDetail});
}

async function init() {
  restoreSavedViewState();
  restorePlaybackSettings();
  updatePlaybackSettingsUI();
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
