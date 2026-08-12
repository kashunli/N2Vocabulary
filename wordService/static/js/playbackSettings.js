import {
  elements,
  state,
} from "./state.js";

export function updatePlaybackSettingsUI() {
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

export function openPlaybackSettings() {
  updatePlaybackSettingsUI();
  elements.settingsBackdrop.classList.add("open");
  elements.settingsBackdrop.setAttribute("aria-hidden", "false");
  elements.postSentenceSilence.focus();
}

export function closePlaybackSettings() {
  elements.settingsBackdrop.classList.remove("open");
  elements.settingsBackdrop.setAttribute("aria-hidden", "true");
  elements.settingsButton.focus();
}
