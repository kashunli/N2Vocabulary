export type PlaybackPhase = "word" | "sentence";
export type PlaybackMode = "words" | "sentences" | "both";
export type PlaybackRunMode = "single" | "consecutive";

export const DEFAULT_SILENCE_MS = 500;
export const DEFAULT_PLAYBACK_RUN_MODE: PlaybackRunMode = "consecutive";

const PLAYBACK_SETTINGS_KEY = "n2-word-service:react-playback-settings:v1";

type StoredPlaybackSettings = {
  postWordSilenceMs?: number;
  postSentenceSilenceMs?: number;
  playbackMode?: PlaybackMode;
  playbackRunMode?: PlaybackRunMode;
};

export type PlaybackSettings = {
  postWordSilence: number;
  postSentenceSilence: number;
  mode: PlaybackMode;
  runMode: PlaybackRunMode;
};

function normalizeSilence(value: unknown) {
  const silence = Number(value);
  return Number.isFinite(silence)
    ? Math.min(3000, Math.max(0, Math.round(silence / 100) * 100))
    : DEFAULT_SILENCE_MS;
}

export function readPlaybackSettings(): PlaybackSettings {
  try {
    const raw = window.localStorage.getItem(PLAYBACK_SETTINGS_KEY);
    const saved = raw ? JSON.parse(raw) as StoredPlaybackSettings : {};
    const mode = saved.playbackMode === "words" || saved.playbackMode === "sentences" || saved.playbackMode === "both"
      ? saved.playbackMode
      : "both";
    const runMode = saved.playbackRunMode === "single" || saved.playbackRunMode === "consecutive"
      ? saved.playbackRunMode
      : DEFAULT_PLAYBACK_RUN_MODE;
    return {
      postWordSilence: normalizeSilence(saved.postWordSilenceMs),
      postSentenceSilence: normalizeSilence(saved.postSentenceSilenceMs),
      mode,
      runMode,
    };
  } catch {
    return {
      postWordSilence: DEFAULT_SILENCE_MS,
      postSentenceSilence: DEFAULT_SILENCE_MS,
      mode: "both",
      runMode: DEFAULT_PLAYBACK_RUN_MODE,
    };
  }
}

export function savePlaybackSettings(
  postWordSilence: number,
  postSentenceSilence: number,
  mode: PlaybackMode,
  runMode: PlaybackRunMode,
) {
  window.localStorage.setItem(PLAYBACK_SETTINGS_KEY, JSON.stringify({
    postWordSilenceMs: postWordSilence,
    postSentenceSilenceMs: postSentenceSilence,
    playbackMode: mode,
    playbackRunMode: runMode,
  }));
}
