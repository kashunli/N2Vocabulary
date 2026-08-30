import {
  createDefaultAudioSequence,
  MAX_SEQUENCE_PAUSE_MS,
  normalizeAudioSequence,
} from "./audioSequence.mjs";
import type { AudioSequenceConfig } from "./audioSequenceTypes";

export type PlaybackPhase = "word" | "sentence";
/** How far automatic playback may continue after the focused occurrence. */
export type PlaybackRunMode = "single" | "continuous";
/** What continuous playback should do after the current visible list ends. */
export type PlaybackEndBehavior = "stop" | "restart-list" | "next-list";

export const DEFAULT_SILENCE_MS = 500;
export const DEFAULT_PLAYBACK_RUN_MODE: PlaybackRunMode = "continuous";
export const DEFAULT_PLAYBACK_END_BEHAVIOR: PlaybackEndBehavior = "stop";

export const PLAYBACK_RUN_MODE_ORDER: PlaybackRunMode[] = [
  "single",
  "continuous",
];

export const PLAYBACK_END_BEHAVIOR_ORDER: PlaybackEndBehavior[] = [
  "stop",
  "restart-list",
  "next-list",
];

export function isPlaybackRunMode(value: unknown): value is PlaybackRunMode {
  return value === "single"
    || value === "continuous";
}

export function isPlaybackEndBehavior(value: unknown): value is PlaybackEndBehavior {
  return value === "stop"
    || value === "restart-list"
    || value === "next-list";
}

export function playbackRunModeLabel(mode: PlaybackRunMode) {
  switch (mode) {
    case "single": return "Manual / single play";
    case "continuous": return "Continuous";
  }
}

export function playbackRunModeDescription(mode: PlaybackRunMode) {
  switch (mode) {
    case "single": return "Play only the focused audio occurrence.";
    case "continuous": return "Play the configured sequence through the current visible list.";
  }
}

const PLAYBACK_SETTINGS_KEY = "n2-word-service:react-playback-settings:v3";
const LEGACY_PLAYBACK_SETTINGS_KEY_V2 = "n2-word-service:react-playback-settings:v2";
const LEGACY_PLAYBACK_SETTINGS_KEY = "n2-word-service:react-playback-settings:v1";

type StoredPlaybackRunMode = PlaybackRunMode | "consecutive" | "list" | "cycle-list" | "next-list";

type StoredPlaybackSettings = {
  postWordSilenceMs?: number;
  postSentenceSilenceMs?: number;
  playbackRunMode?: StoredPlaybackRunMode;
  playbackEndBehavior?: PlaybackEndBehavior;
  sequence?: unknown;
};

export type PlaybackSettings = {
  postWordSilence: number;
  postSentenceSilence: number;
  runMode: PlaybackRunMode;
  endBehavior: PlaybackEndBehavior;
  sequence: AudioSequenceConfig;
};

function normalizeSilence(value: unknown) {
  const silence = Number(value);
  return Number.isFinite(silence)
    ? Math.min(MAX_SEQUENCE_PAUSE_MS, Math.max(0, Math.round(silence / 100) * 100))
    : DEFAULT_SILENCE_MS;
}

function normalizeEndBehavior(value: unknown) {
  return isPlaybackEndBehavior(value) ? value : DEFAULT_PLAYBACK_END_BEHAVIOR;
}

function normalizeRunSettings(
  storedMode: StoredPlaybackRunMode | undefined,
  storedEndBehavior: unknown,
) {
  const configuredEndBehavior = normalizeEndBehavior(storedEndBehavior);
  switch (storedMode) {
    case "single":
      return {runMode: "single" as const, endBehavior: configuredEndBehavior};
    case "continuous":
      return {runMode: "continuous" as const, endBehavior: configuredEndBehavior};
    // The previous four-mode schema stored the list boundary as part of the
    // run mode. Convert those values into the new two-field representation.
    case "cycle-list":
      return {runMode: "continuous" as const, endBehavior: "restart-list" as const};
    case "next-list":
      return {runMode: "continuous" as const, endBehavior: "next-list" as const};
    case "consecutive":
    case "list":
    default:
      return {runMode: DEFAULT_PLAYBACK_RUN_MODE, endBehavior: configuredEndBehavior};
  }
}

export function readPlaybackSettings(): PlaybackSettings {
  try {
    const storageKeys = [
      PLAYBACK_SETTINGS_KEY,
      LEGACY_PLAYBACK_SETTINGS_KEY_V2,
      LEGACY_PLAYBACK_SETTINGS_KEY,
    ];
    const sourceKey = storageKeys.find((key) => window.localStorage.getItem(key));
    const raw = sourceKey ? window.localStorage.getItem(sourceKey) : null;
    const parsed = raw ? JSON.parse(raw) : {};
    const saved = parsed && typeof parsed === "object" ? parsed as StoredPlaybackSettings : {};
    const postWordSilence = normalizeSilence(saved.postWordSilenceMs);
    const postSentenceSilence = normalizeSilence(saved.postSentenceSilenceMs);
    const {runMode, endBehavior} = normalizeRunSettings(
      saved.playbackRunMode,
      saved.playbackEndBehavior,
    );
    const settings = {
      postWordSilence,
      postSentenceSilence,
      runMode,
      endBehavior,
      sequence: normalizeAudioSequence(saved.sequence, postWordSilence, postSentenceSilence) as AudioSequenceConfig,
    };

    // Write a canonical v3 value as soon as an older or partially populated
    // record is read. The old keys remain harmless compatibility sources, but
    // all future writes contain only the two run modes and one end behavior.
    if (sourceKey && (
      sourceKey !== PLAYBACK_SETTINGS_KEY
      || saved.playbackRunMode !== runMode
      || saved.playbackEndBehavior !== endBehavior
    )) {
      try {
        savePlaybackSettings(
          postWordSilence,
          postSentenceSilence,
          runMode,
          endBehavior,
          settings.sequence,
        );
      } catch {
        // Reading the preference should still work when localStorage becomes
        // read-only after the initial getItem calls.
      }
    }
    return settings;
  } catch {
    return {
      postWordSilence: DEFAULT_SILENCE_MS,
      postSentenceSilence: DEFAULT_SILENCE_MS,
      runMode: DEFAULT_PLAYBACK_RUN_MODE,
      endBehavior: DEFAULT_PLAYBACK_END_BEHAVIOR,
      sequence: createDefaultAudioSequence(DEFAULT_SILENCE_MS, DEFAULT_SILENCE_MS) as AudioSequenceConfig,
    };
  }
}

export function savePlaybackSettings(
  postWordSilence: number,
  postSentenceSilence: number,
  runMode: PlaybackRunMode,
  endBehavior: PlaybackEndBehavior,
  sequence = createDefaultAudioSequence(postWordSilence, postSentenceSilence),
) {
  window.localStorage.setItem(PLAYBACK_SETTINGS_KEY, JSON.stringify({
    postWordSilenceMs: postWordSilence,
    postSentenceSilenceMs: postSentenceSilence,
    playbackRunMode: runMode,
    playbackEndBehavior: endBehavior,
    sequence,
  }));
}
