import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowCounterClockwise, ListBullets, Pause, Play, Queue, Repeat, RepeatOnce, SkipBack, SkipForward } from "@phosphor-icons/react";

import { useAudioBufferPlayer } from "./useAudioBufferPlayer";
import { LineWaveform } from "./LineWaveform";
import { detectSilenceGapsMs } from "./waveform.mjs";
import {
  listenForNativeAudioState,
  nativeAudioAvailable,
  nativeAudioState,
  pauseNativeAudio,
  playNativeAudioQueue,
  resumeNativeAudio,
  seekNativeAudio,
  type NativeAudioQueueItem,
  type NativeAudioState,
} from "./nativeAudio";
import {
  nextPlaybackRunMode,
  playbackRunModeLabel,
  type PlaybackRunMode,
} from "./playbackSettings";
import type { MarkStatus } from "../study/markStatus";
import type { AudioTarget } from "../../types";

interface RailPlayerProps {
  target: AudioTarget | null;
  autoPlay: boolean;
  isPlaybackActive: boolean;
  playbackRunMode: PlaybackRunMode;
  markStatus: MarkStatus;
  nativeQueue: NativeAudioQueueItem[];
  onNativeQueueItem: (id: string) => void;
  onNativeQueueComplete: () => void;
  playRequest: number;
  replayRequest: number;
  pauseRequest: number;
  onEnded: () => void;
  onPlayingChange: (playing: boolean) => void;
  onToggleMark: (key: "known" | "flagged") => void | Promise<void>;
  onTogglePlayback: () => void;
  onTogglePlaybackRunMode: () => void;
  onCancelSilence: () => void;
  onReplay: () => void;
  onPrevious: () => void;
  onNext: () => void;
  canPrevious: boolean;
  canNext: boolean;
}

function isNativeActive(state: NativeAudioState | undefined) {
  return state?.status === "playing" || state?.status === "gap";
}

function PlaybackRunModeIcon({mode}: {mode: PlaybackRunMode}) {
  switch (mode) {
    // Single uses a repeat-once symbol so the mode communicates its boundary.
    case "single": return <RepeatOnce size={18} weight="bold" />;
    case "list": return <ListBullets size={18} weight="bold" />;
    case "cycle-list": return <Repeat size={18} weight="bold" />;
    case "next-list": return <Queue size={18} weight="bold" />;
  }
}

export function RailPlayer({
  target,
  autoPlay,
  isPlaybackActive,
  playbackRunMode,
  markStatus,
  nativeQueue,
  onNativeQueueItem,
  onNativeQueueComplete,
  playRequest,
  replayRequest,
  pauseRequest,
  onEnded,
  onPlayingChange,
  onToggleMark,
  onTogglePlayback,
  onTogglePlaybackRunMode,
  onCancelSilence,
  onReplay,
  onPrevious,
  onNext,
  canPrevious,
  canNext,
}: RailPlayerProps) {
  const [activeUrl, setActiveUrl] = useState<string>();
  const [error, setError] = useState("");
  const [nativeState, setNativeState] = useState<NativeAudioState>();
  const finish = useCallback(() => onEnded(), [onEnded]);
  const player = useAudioBufferPlayer(activeUrl, finish);
  const nativeAvailable = nativeAudioAvailable();
  const currentTimeRef = useRef(player.currentTime);
  const lastPlayRequest = useRef(playRequest);
  const lastReplayRequest = useRef(replayRequest);
  const lastPauseRequest = useRef(pauseRequest);
  const lastTargetKey = useRef<string | undefined>(undefined);
  const pendingTargetPlay = useRef(false);
  currentTimeRef.current = player.currentTime;

  // A background service keeps progressing even when the WebView cannot paint.
  // Pull a snapshot when it becomes visible so the active card catches up
  // after an unlock without trying to reconstruct skipped JS timers.
  useEffect(() => {
    if (!nativeAvailable) return undefined;
    let disposed = false;
    const acceptState = (state: NativeAudioState) => {
      if (disposed) return;
      setNativeState(state);
      if (state.itemId && (state.status === "playing" || state.status === "ready")) {
        onNativeQueueItem(state.itemId);
      }
      if (state.status === "completed") onNativeQueueComplete();
      if (state.error) setError(state.error);
    };
    const refresh = () => void nativeAudioState().then((state) => state && acceptState(state));
    refresh();
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") refresh();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    let subscription: {remove(): Promise<void> | void} | undefined;
    void listenForNativeAudioState(acceptState).then((nextSubscription) => {
      subscription = nextSubscription;
    });
    return () => {
      disposed = true;
      document.removeEventListener("visibilitychange", onVisibilityChange);
      void subscription?.remove();
    };
  }, [nativeAvailable, onNativeQueueComplete, onNativeQueueItem]);

  const effectivePlaying = nativeAvailable ? isNativeActive(nativeState) : player.isPlaying;
  useEffect(() => {
    onPlayingChange(effectivePlaying);
  }, [effectivePlaying, onPlayingChange]);

  // The same word or sentence can appear more than once in a recipe. Include
  // the occurrence identity so repeated rows restart even when their URL is
  // unchanged.
  const targetKey = target
    ? `${target.entry.item_uuid}:${target.phase}:${target.sequenceOccurrenceId || "direct"}:${target.url}`
    : "";

  useEffect(() => {
    setError("");
    setActiveUrl(target?.url);
    if (targetKey !== lastTargetKey.current) {
      // Android queue transitions update the selected target, but must not
      // replace the native queue with a one-item request.
      pendingTargetPlay.current = !!target && autoPlay && !nativeAvailable;
      lastTargetKey.current = targetKey;
    }
  }, [autoPlay, nativeAvailable, target?.url, targetKey]);

  const nativeItemsForRun = useCallback(() => {
    if (playbackRunMode !== "single") return nativeQueue;
    const first = nativeQueue[0];
    return first ? [{...first, pauseAfterMs: 0}] : [];
  }, [nativeQueue, playbackRunMode]);

  const playFrom = useCallback(async (offset?: number) => {
    if (!target || !activeUrl) return;
    try {
      if (nativeAvailable) {
        const items = nativeItemsForRun();
        if (!items.length) return;
        await playNativeAudioQueue(items);
        if (offset && offset > 0) await seekNativeAudio(offset * 1000);
        return;
      }
      if (!player.audioBuffer) return;
      await player.playRange({
        start: 0,
        end: player.audioBuffer.duration,
        offset: offset ?? (currentTimeRef.current >= player.audioBuffer.duration ? 0 : currentTimeRef.current),
        segmentId: `${target.entry.entry_id}:${target.phase}:${target.sequenceOccurrenceId || "direct"}`,
      });
    } catch {
      setError("Audio could not be played.");
    }
  }, [activeUrl, nativeAvailable, nativeItemsForRun, player.audioBuffer, player.playRange, target]);

  // Clicking the wave while paused starts from that point. Android receives
  // the seek after creating the native queue, rather than React starting an
  // AudioBufferSourceNode that cannot outlive the locked WebView.
  const handleWaveSeekPlay = useCallback((time: number) => {
    if (effectivePlaying) return;
    onCancelSilence();
    void playFrom(time);
  }, [effectivePlaying, onCancelSilence, playFrom]);

  // The hosted browser retains the existing decoded-buffer route. In the APK,
  // React sends one materialized queue and Android advances it in the service.
  useEffect(() => {
    if (nativeAvailable) return;
    if (
      !pendingTargetPlay.current
      || !autoPlay
      || !target
      || !activeUrl
      || activeUrl !== target.url
      || player.loadedAudioUrl !== activeUrl
      || !player.audioBuffer
      || player.isPlaying
    ) {
      return;
    }
    pendingTargetPlay.current = false;
    lastPlayRequest.current = playRequest;
    void playFrom(0);
  }, [activeUrl, autoPlay, nativeAvailable, playFrom, playRequest, player.audioBuffer, player.isPlaying, player.loadedAudioUrl, target?.url, targetKey]);

  useEffect(() => {
    if (playRequest === lastPlayRequest.current) return;
    lastPlayRequest.current = playRequest;
    if (!autoPlay || !target) return;
    if (nativeAvailable) {
      // Resume the exact native queue (including a paused silence) only when
      // the selected React cue still matches the service's current cue. A
      // navigation request has a different first queue item and must replace it.
      if (
        (nativeState?.status === "paused" || nativeState?.status === "gap-paused")
        && nativeState.itemId === nativeQueue[0]?.id
      ) {
        void resumeNativeAudio();
        return;
      }
      void playFrom();
      return;
    }
    if (activeUrl === target.url && player.loadedAudioUrl === activeUrl && player.audioBuffer) void playFrom();
  }, [activeUrl, autoPlay, nativeAvailable, nativeQueue, nativeState?.itemId, nativeState?.status, playFrom, playRequest, player.audioBuffer, player.loadedAudioUrl, target]);

  useEffect(() => {
    if (replayRequest === lastReplayRequest.current) return;
    lastReplayRequest.current = replayRequest;
    if (nativeAvailable) {
      void playFrom(0);
      return;
    }
    if (player.audioBuffer) {
      player.setPosition(0);
      void playFrom(0);
    }
  }, [nativeAvailable, playFrom, player.audioBuffer, player.setPosition, replayRequest]);

  useEffect(() => {
    if (pauseRequest === lastPauseRequest.current) return;
    lastPauseRequest.current = pauseRequest;
    if (nativeAvailable) {
      void pauseNativeAudio();
      return;
    }
    player.pause();
  }, [nativeAvailable, pauseRequest, player.pause]);

  // React still decodes an audio buffer for the waveform, but native service
  // events become the source of displayed playback time in the APK.
  const duration = player.audioBuffer?.duration || (nativeState?.durationMs || 0) / 1000;
  const currentTime = nativeAvailable ? (nativeState?.positionMs || 0) / 1000 : player.currentTime;
  const silenceGaps = useMemo(() => {
    if (!player.audioBuffer) return [];
    const channels = Array.from(
      {length: player.audioBuffer.numberOfChannels},
      (_, index) => player.audioBuffer!.getChannelData(index),
    );
    return detectSilenceGapsMs(
      channels,
      player.audioBuffer.sampleRate,
      0,
      duration * 1000,
    ).map(({startMs, endMs}) => ({start_ms: startMs, end_ms: endMs}));
  }, [duration, player.audioBuffer]);
  const canPlay = nativeAvailable ? !!target : !!player.audioBuffer;

  const handleSeek = useCallback((time: number) => {
    if (nativeAvailable) {
      void seekNativeAudio(time * 1000);
      return;
    }
    void player.seek(time);
  }, [nativeAvailable, player.seek]);

  const nativeStatus = nativeState?.status === "gap"
    ? "Native queue pause"
    : nativeState?.status === "gap-paused"
      ? "Native queue paused"
      : nativeState?.status === "playing"
        ? "Native background player"
        : "";

  return (
    <section className="react-player" aria-label="Playback controls">
      <div className="react-player-wave-row">
        <button type="button" className="react-player-primary" onClick={onTogglePlayback} disabled={!canPlay} aria-keyshortcuts="Space" aria-label={isPlaybackActive ? "Pause" : "Play"} title={`${isPlaybackActive ? "Pause" : "Play"} (Space)`}>
          {isPlaybackActive ? <Pause size={24} weight="fill" /> : <Play size={24} weight="fill" />}
        </button>
        <LineWaveform
          audioBuffer={player.audioBuffer}
          loadFailed={player.loadFailed}
          start={0}
          end={duration || 0.01}
          currentTime={currentTime}
          silenceGaps={silenceGaps}
          vadNonSpeechIntervals={[]}
          onSeek={handleSeek}
          onSeekPlay={handleWaveSeekPlay}
          onNavigationPointsChange={() => {}}
        />
      </div>
      <div className="react-player-controls">
        <button type="button" onClick={onPrevious} disabled={!canPrevious} aria-label="Play previous word or sentence" title="Previous (A / ←)"><SkipBack size={18} weight="fill" /></button>
        <button type="button" onClick={onReplay} disabled={!canPlay} aria-label="Replay focused word or sentence" title="Replay (R)"><ArrowCounterClockwise size={18} weight="bold" /></button>
        <button type="button" onClick={onNext} disabled={!canNext} aria-label="Play next word or sentence" title="Next (D / →)"><SkipForward size={18} weight="fill" /></button>
        <button
          type="button"
          className={playbackRunMode === "single" ? "" : "is-selected"}
          onClick={onTogglePlaybackRunMode}
          aria-pressed={playbackRunMode !== "single"}
          aria-label={`Playback mode: ${playbackRunModeLabel(playbackRunMode)}. Switch to ${playbackRunModeLabel(nextPlaybackRunMode(playbackRunMode))}.`}
          title={`Playback mode: ${playbackRunModeLabel(playbackRunMode)}. Click to switch to ${playbackRunModeLabel(nextPlaybackRunMode(playbackRunMode))}.`}
        >
          <PlaybackRunModeIcon mode={playbackRunMode} />
        </button>
        <span className="react-player-controls-sep" aria-hidden="true" />
        <button type="button" className={`mark-known${markStatus === "known" ? " is-on" : ""}`} onClick={() => void onToggleMark("known")} disabled={!target} aria-label="Mark as known" title="Mark as known" aria-pressed={markStatus === "known"}>✓</button>
        <button type="button" className={`mark-flagged${markStatus === "flagged" ? " is-on" : ""}`} onClick={() => void onToggleMark("flagged")} disabled={!target} aria-label="Flag for review" title="Flag for review" aria-pressed={markStatus === "flagged"}>⚑</button>
        <span className="react-player-status">{error || nativeState?.error || nativeStatus || `${playbackRunModeLabel(playbackRunMode)} · Click the wave to seek or play · Space to play/pause`}</span>
      </div>
    </section>
  );
}
