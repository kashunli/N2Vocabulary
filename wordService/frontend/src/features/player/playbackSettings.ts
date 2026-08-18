import { createDefaultAudioSequence, normalizeAudioSequence } from "./audioSequence.mjs";
import type { AudioSequenceConfig } from "./audioSequenceTypes";

export type PlaybackPhase = "word" | "sentence";
export type PlaybackRunMode = "single" | "consecutive";

export const DEFAULT_SILENCE_MS = 500;
export const DEFAULT_PLAYBACK_RUN_MODE: PlaybackRunMode = "consecutive";

const PLAYBACK_SETTINGS_KEY = "n2-word-service:react-playback-settings:v2";
const LEGACY_PLAYBACK_SETTINGS_KEY = "n2-word-service:react-playback-settings:v1";

type StoredPlaybackSettings = {
  postWordSilenceMs?: number;
  postSentenceSilenceMs?: number;
  playbackRunMode?: PlaybackRunMode;
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
    ? Math.min(3000, Math.max(0, Math.round(silence / 100) * 100))
    : DEFAULT_SILENCE_MS;
}

export function readPlaybackSettings(): PlaybackSettings {
  try {
    const raw = window.localStorage.getItem(PLAYBACK_SETTINGS_KEY)
      || window.localStorage.getItem(LEGACY_PLAYBACK_SETTINGS_KEY);
    const saved = raw ? JSON.parse(raw) as StoredPlaybackSettings : {};
    const postWordSilence = normalizeSilence(saved.postWordSilenceMs);
    const postSentenceSilence = normalizeSilence(saved.postSentenceSilenceMs);
    const runMode = saved.playbackRunMode === "single" || saved.playbackRunMode === "consecutive"
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
