import {
  createDefaultAudioSequence,
  MAX_SEQUENCE_PAUSE_MS,
  normalizeAudioSequence,
} from "./audioSequence.mjs";
import type { AudioSequenceConfig } from "./audioSequenceTypes";

export type PlaybackPhase = "word" | "sentence";
/** How far automatic playback may continue after the focused occurrence. */
export type PlaybackRunMode = "single" | "list" | "cycle-list" | "next-list";

export const DEFAULT_SILENCE_MS = 500;
export const DEFAULT_PLAYBACK_RUN_MODE: PlaybackRunMode = "list";

export const PLAYBACK_RUN_MODE_ORDER: PlaybackRunMode[] = [
  "single",
  "list",
  "cycle-list",
  "next-list",
];

export function isPlaybackRunMode(value: unknown): value is PlaybackRunMode {
  return value === "single"
    || value === "list"
    || value === "cycle-list"
    || value === "next-list";
}

export function playbackRunModeLabel(mode: PlaybackRunMode) {
  switch (mode) {
    case "single": return "Single audio";
    case "list": return "Play list once";
    case "cycle-list": return "Cycle this list";
    case "next-list": return "Continue to next list";
  }
}

export function playbackRunModeDescription(mode: PlaybackRunMode) {
  switch (mode) {
    case "single": return "Stop after the focused audio occurrence.";
    case "list": return "Play every available row in this list once, then stop.";
    case "cycle-list": return "When this list ends, start it again from the beginning.";
    case "next-list": return "When this section ends, continue with the following section.";
  }
}

export function nextPlaybackRunMode(mode: PlaybackRunMode) {
  const currentIndex = PLAYBACK_RUN_MODE_ORDER.indexOf(mode);
  return PLAYBACK_RUN_MODE_ORDER[(currentIndex + 1) % PLAYBACK_RUN_MODE_ORDER.length];
}

const PLAYBACK_SETTINGS_KEY = "n2-word-service:react-playback-settings:v2";
const LEGACY_PLAYBACK_SETTINGS_KEY = "n2-word-service:react-playback-settings:v1";

type StoredPlaybackSettings = {
  postWordSilenceMs?: number;
  postSentenceSilenceMs?: number;
  playbackRunMode?: PlaybackRunMode | "consecutive";
  sequence?: unknown;
};

export type PlaybackSettings = {
  postWordSilence: number;
  postSentenceSilence: number;
  runMode: PlaybackRunMode;
  sequence: AudioSequenceConfig;
};

function normalizeSilence(value: unknown) {
  const silence = Number(value);
  return Number.isFinite(silence)
    ? Math.min(MAX_SEQUENCE_PAUSE_MS, Math.max(0, Math.round(silence / 100) * 100))
    : DEFAULT_SILENCE_MS;
}

export function readPlaybackSettings(): PlaybackSettings {
  try {
    const raw = window.localStorage.getItem(PLAYBACK_SETTINGS_KEY)
      || window.localStorage.getItem(LEGACY_PLAYBACK_SETTINGS_KEY);
    const saved = raw ? JSON.parse(raw) as StoredPlaybackSettings : {};
    const postWordSilence = normalizeSilence(saved.postWordSilenceMs);
    const postSentenceSilence = normalizeSilence(saved.postSentenceSilenceMs);
    // v1/v2 called the one-pass list mode "consecutive". Keep learners'
    // existing preference when adding the two new list-boundary modes.
    const runMode = saved.playbackRunMode === "consecutive"
      ? "list"
      : isPlaybackRunMode(saved.playbackRunMode)
        ? saved.playbackRunMode
        : DEFAULT_PLAYBACK_RUN_MODE;
    return {
      postWordSilence,
      postSentenceSilence,
      runMode,
      sequence: normalizeAudioSequence(saved.sequence, postWordSilence, postSentenceSilence) as AudioSequenceConfig,
    };
  } catch {
    return {
      postWordSilence: DEFAULT_SILENCE_MS,
      postSentenceSilence: DEFAULT_SILENCE_MS,
      runMode: DEFAULT_PLAYBACK_RUN_MODE,
      sequence: createDefaultAudioSequence(DEFAULT_SILENCE_MS, DEFAULT_SILENCE_MS) as AudioSequenceConfig,
    };
  }
}

export function savePlaybackSettings(
  postWordSilence: number,
  postSentenceSilence: number,
  runMode: PlaybackRunMode,
  sequence = createDefaultAudioSequence(postWordSilence, postSentenceSilence),
) {
  window.localStorage.setItem(PLAYBACK_SETTINGS_KEY, JSON.stringify({
    postWordSilenceMs: postWordSilence,
    postSentenceSilenceMs: postSentenceSilence,
    playbackRunMode: runMode,
    sequence,
  }));
}
