/**
 * The hosted browser keeps working without Capacitor.  The Android APK injects
 * this small custom plugin, which moves actual sound production and caching to
 * a foreground Media3 service while React remains the learner-facing UI.
 */
export interface NativeAudioQueueItem {
  id: string;
  title: string;
  url: string;
  /** Database identity used to keep the native compressed-audio cache fresh. */
  audioId?: number;
  pauseAfterMs: number;
}

export interface NativeAudioState {
  status: "idle" | "ready" | "playing" | "paused" | "gap" | "gap-paused" | "completed" | "error";
  itemId: string;
  url: string;
  queueIndex: number;
  queueLength: number;
  positionMs: number;
  durationMs: number;
  error?: string;
}

interface NativeAudioPlugin {
  playQueue(options: {items: NativeAudioQueueItem[]}): Promise<void>;
  pause(): Promise<void>;
  resume(): Promise<void>;
  seek(options: {positionMs: number}): Promise<void>;
  stop(): Promise<void>;
  getState(): Promise<NativeAudioState>;
  addListener(
    eventName: "stateChange",
    listener: (state: NativeAudioState) => void,
  ): Promise<{remove(): Promise<void> | void}>;
}

type CapacitorGlobal = {
  isNativePlatform?: () => boolean;
  Plugins?: {NativeAudio?: NativeAudioPlugin};
};

function plugin(): NativeAudioPlugin | undefined {
  const capacitor = (globalThis as typeof globalThis & {Capacitor?: CapacitorGlobal}).Capacitor;
  if (!capacitor?.isNativePlatform?.()) return undefined;
  return capacitor.Plugins?.NativeAudio;
}

export function nativeAudioAvailable() {
  return !!plugin();
}

/** Native services receive absolute HTTP(S) URLs; a WebView can resolve a
 * relative `/audio/...` URL itself, but ExoPlayer cannot infer its origin. */
export function nativeAudioUrl(url: string, audioId?: number) {
  const absolute = new URL(url, globalThis.location?.href || "https://invalid.local/");
  if (audioId !== undefined && !absolute.searchParams.has("v")) {
    absolute.searchParams.set("v", String(audioId));
  }
  return absolute.href;
}

export async function playNativeAudioQueue(items: NativeAudioQueueItem[]) {
  const nativeAudio = plugin();
  if (!nativeAudio) throw new Error("Native audio playback is unavailable.");
  await nativeAudio.playQueue({
    items: items.map((item) => ({...item, url: nativeAudioUrl(item.url, item.audioId)})),
  });
}

export async function pauseNativeAudio() {
  await plugin()?.pause();
}

export async function resumeNativeAudio() {
  await plugin()?.resume();
}

export async function seekNativeAudio(positionMs: number) {
  await plugin()?.seek({positionMs: Math.max(0, Math.round(positionMs))});
}

export async function nativeAudioState(): Promise<NativeAudioState | undefined> {
  return plugin()?.getState();
}

export async function listenForNativeAudioState(
  listener: (state: NativeAudioState) => void,
) {
  return plugin()?.addListener("stateChange", listener);
}
