export type PlaybackPhase = "word" | "sentence";
export type PlaybackMode = "words" | "sentences" | "both";

export const DEFAULT_SILENCE_MS = 500;

const PLAYBACK_SETTINGS_KEY = "n2-word-service:react-playback-settings:v1";

type StoredPlaybackSettings = {
  postWordSilenceMs?: number;
  postSentenceSilenceMs?: number;
  playbackMode?: PlaybackMode;
};

export type PlaybackSettings = {
  postWordSilence: number;
  postSentenceSilence: number;
  mode: PlaybackMode;
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
    return {
      postWordSilence: normalizeSilence(saved.postWordSilenceMs),
      postSentenceSilence: normalizeSilence(saved.postSentenceSilenceMs),
      mode,
    };
  } catch {
    return {postWordSilence: DEFAULT_SILENCE_MS, postSentenceSilence: DEFAULT_SILENCE_MS, mode: "both"};
  }
}

export function savePlaybackSettings(postWordSilence: number, postSentenceSilence: number, mode: PlaybackMode) {
  window.localStorage.setItem(PLAYBACK_SETTINGS_KEY, JSON.stringify({
    postWordSilenceMs: postWordSilence,
    postSentenceSilenceMs: postSentenceSilence,
    playbackMode: mode,
  }));
}
