import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowCounterClockwise, List, Pause, Play, SkipBack, SkipForward } from "@phosphor-icons/react";

import { useI18n } from "../../i18n";
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
import type { MarkStatus } from "../study/markStatus";
import type { AudioTarget } from "../../types";
import type { PlaybackRunMode } from "./playbackSettings";

interface RailPlayerProps {
  target: AudioTarget | null;
  autoPlay: boolean;
  isPlaybackActive: boolean;
  playbackRunMode: PlaybackRunMode;
  blurred: boolean;
  listVisible: boolean;
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
  onToggleBlur: () => void;
  onToggleList: () => void;
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

export function RailPlayer({
  target,
  autoPlay,
  isPlaybackActive,
  playbackRunMode,
  blurred,
  listVisible,
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
  onToggleBlur,
  onToggleList,
  onCancelSilence,
  onReplay,
  onPrevious,
  onNext,
  canPrevious,
  canNext,
}: RailPlayerProps) {
  const {copy, localizeMessage} = useI18n();
  const [activeUrl, setActiveUrl] = useState<string>();
  const [activeAudioId, setActiveAudioId] = useState<number>();
  const [error, setError] = useState("");
  const [nativeState, setNativeState] = useState<NativeAudioState>();
  const finish = useCallback(() => onEnded(), [onEnded]);
  const player = useAudioBufferPlayer(activeUrl, activeAudioId, finish);
  const nativeAvailable = nativeAudioAvailable();
  const reportNativeError = useCallback(() => setError(copy.errors.audioPlayback), [copy.errors.audioPlayback]);
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
    const refresh = () => void nativeAudioState()
      .then((state) => state && acceptState(state))
      .catch(() => {});
    refresh();
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") refresh();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    let subscription: {remove(): Promise<void> | void} | undefined;
    const releaseSubscription = (candidate: typeof subscription) => {
      try {
        void Promise.resolve(candidate?.remove()).catch(() => {});
      } catch {
        // The native plugin may already be gone during Activity teardown.
      }
    };
    void listenForNativeAudioState(acceptState)
      .then((nextSubscription) => {
        if (disposed) {
          releaseSubscription(nextSubscription);
          return;
        }
        subscription = nextSubscription;
      })
      .catch(() => {});
    return () => {
      disposed = true;
      document.removeEventListener("visibilitychange", onVisibilityChange);
      releaseSubscription(subscription);
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
    ? `${target.entry.item_uuid}:${target.phase}:${target.sequenceOccurrenceId || "direct"}:${target.audioId ?? "missing-id"}:${target.url}`
    : "";

  useEffect(() => {
    setError("");
    setActiveUrl(target?.url);
    setActiveAudioId(target?.audioId);
    if (targetKey !== lastTargetKey.current) {
      // Android queue transitions update the selected target, but must not
      // replace the native queue with a one-item request.
      pendingTargetPlay.current = !!target && autoPlay && !nativeAvailable;
      lastTargetKey.current = targetKey;
    }
  }, [autoPlay, nativeAvailable, target?.audioId, target?.url, targetKey]);

  const nativeItemsForRun = useCallback(() => {
    if (playbackRunMode === "continuous") return nativeQueue;
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
      setError(copy.errors.audioPlayback);
    }
  }, [activeUrl, copy.errors.audioPlayback, nativeAvailable, nativeItemsForRun, player.audioBuffer, player.playRange, target]);

  // Clicking the wave while paused starts from that point. If Android still
  // owns the selected paused item, seek it in place; rebuilding the queue here
  // would reset to its first item before the seek and sound like a full replay.
  const handleWaveSeekPlay = useCallback((time: number) => {
    if (effectivePlaying) return;
    onCancelSilence();
    if (
      nativeAvailable
      && (nativeState?.status === "paused" || nativeState?.status === "ready")
      && nativeState.itemId === nativeQueue[0]?.id
    ) {
      void seekNativeAudio(time * 1000)
        .then(() => resumeNativeAudio())
        .catch(() => reportNativeError());
      return;
    }
    void playFrom(time);
  }, [effectivePlaying, nativeAvailable, nativeQueue, nativeState?.itemId, nativeState?.status, onCancelSilence, playFrom, reportNativeError]);

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
      || player.loadedAudioId !== target.audioId
      || !player.audioBuffer
      || player.isPlaying
    ) {
      return;
    }
    pendingTargetPlay.current = false;
    lastPlayRequest.current = playRequest;
    void playFrom(0);
  }, [activeUrl, autoPlay, nativeAvailable, playFrom, playRequest, player.audioBuffer, player.isPlaying, player.loadedAudioId, player.loadedAudioUrl, target?.audioId, target?.url, targetKey]);

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
        void resumeNativeAudio().catch(() => reportNativeError());
        return;
      }
      void playFrom();
      return;
    }
    if (activeUrl === target.url && player.loadedAudioUrl === activeUrl && player.loadedAudioId === target.audioId && player.audioBuffer) void playFrom();
  }, [activeUrl, autoPlay, nativeAvailable, nativeQueue, nativeState?.itemId, nativeState?.status, playFrom, playRequest, player.audioBuffer, player.loadedAudioId, player.loadedAudioUrl, reportNativeError, target]);

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
      void pauseNativeAudio().catch(() => reportNativeError());
      return;
    }
    player.pause();
  }, [nativeAvailable, pauseRequest, player.pause, reportNativeError]);

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
      // A paused waveform drag is finalized by handleWaveSeekPlay. Deferring
      // this native call avoids racing a seek with the resume operation above.
      if (effectivePlaying) void seekNativeAudio(time * 1000).catch(() => reportNativeError());
      return;
    }
    void player.seek(time);
  }, [effectivePlaying, nativeAvailable, player.seek, reportNativeError]);

  const nativeStatus = nativeState?.status === "gap"
    ? copy.player.nativeQueuePause
    : nativeState?.status === "gap-paused"
      ? copy.player.nativeQueuePaused
      : nativeState?.status === "playing"
        ? copy.player.nativeBackgroundPlayer
        : "";
  const currentModeLabel = copy.player.modeLabel(playbackRunMode);
  return (
    <section className="react-player" aria-label={copy.player.controlsLabel}>
      <div className="react-player-wave-row">
        <button type="button" className="react-player-primary" onClick={onTogglePlayback} disabled={!canPlay} aria-keyshortcuts="Space" aria-label={isPlaybackActive ? copy.player.pause : copy.player.play} title={`${isPlaybackActive ? copy.player.pause : copy.player.play} (Space)`}>
          {isPlaybackActive ? <Pause size={24} weight="fill" /> : <Play size={24} weight="fill" />}
        </button>
        <LineWaveform
          audioBuffer={player.audioBuffer}
          loadFailed={player.loadFailed}
          start={0}
          end={duration || 0.01}
          currentTime={currentTime}
          smoothPlayback={nativeAvailable && nativeState?.status === "playing"}
          silenceGaps={silenceGaps}
          vadNonSpeechIntervals={[]}
          onSeek={handleSeek}
          onSeekPlay={handleWaveSeekPlay}
          onNavigationPointsChange={() => {}}
        />
      </div>
      <div className="react-player-controls">
        <button type="button" onClick={onPrevious} disabled={!canPrevious} aria-label={copy.player.previousAria} title={copy.player.previousTitle}><SkipBack size={18} weight="fill" /></button>
        <button type="button" onClick={onReplay} disabled={!canPlay} aria-label={copy.player.replayAria} title={copy.player.replayTitle}><ArrowCounterClockwise size={18} weight="bold" /></button>
        <button type="button" onClick={onNext} disabled={!canNext} aria-label={copy.player.nextAria} title={copy.player.nextTitle}><SkipForward size={18} weight="fill" /></button>
        <span className="react-player-controls-sep" aria-hidden="true" />
        <div className="react-player-control-group react-player-mark-controls">
          <button type="button" className={`mark-known${markStatus === "known" ? " is-on" : ""}`} onClick={() => void onToggleMark("known")} disabled={!target} aria-label={copy.player.markKnown} title={copy.player.markKnown} aria-pressed={markStatus === "known"}>✓</button>
          <button type="button" className={`mark-flagged${markStatus === "flagged" ? " is-on" : ""}`} onClick={() => void onToggleMark("flagged")} disabled={!target} aria-label={copy.player.markFlagged} title={copy.player.markFlagged} aria-pressed={markStatus === "flagged"}>⚑</button>
        </div>
        <span className="react-player-controls-sep" aria-hidden="true" />
        <div className="react-player-control-group react-player-view-controls">
          <button type="button" className={`react-blur-toggle${blurred ? " is-selected" : ""}`} onClick={onToggleBlur} aria-pressed={blurred} aria-label={copy.blurStudyContent} title={copy.blurStudyContent}>B</button>
          <button type="button" className={`react-list-toggle${listVisible ? " is-selected" : ""}`} onClick={onToggleList} aria-pressed={listVisible} aria-label={listVisible ? copy.hideVocabularyList : copy.showVocabularyList} title={listVisible ? copy.hideVocabularyList : copy.showVocabularyList}><List size={18} weight="bold" /></button>
        </div>
        <span className="react-player-status">{error || (nativeState?.error ? localizeMessage(nativeState.error) : "") || nativeStatus || copy.player.defaultStatus(currentModeLabel)}</span>
      </div>
    </section>
  );
}
