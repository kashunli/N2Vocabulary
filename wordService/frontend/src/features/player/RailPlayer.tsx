import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowCounterClockwise, Pause, Play, Repeat, RepeatOnce, SkipBack, SkipForward } from "@phosphor-icons/react";

import { useAudioBufferPlayer } from "./useAudioBufferPlayer";
import { LineWaveform } from "./LineWaveform";
import { detectSilenceGapsMs } from "./waveform.mjs";
import type { PlaybackRunMode } from "./playbackSettings";
import type { MarkStatus } from "../study/markStatus";
import type { AudioTarget } from "../../types";

interface RailPlayerProps {
  target: AudioTarget | null;
  autoPlay: boolean;
  isPlaybackActive: boolean;
  playbackRunMode: PlaybackRunMode;
  markStatus: MarkStatus;
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

export function RailPlayer({
  target,
  autoPlay,
  isPlaybackActive,
  playbackRunMode,
  markStatus,
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
  const finish = useCallback(() => onEnded(), [onEnded]);
  const player = useAudioBufferPlayer(activeUrl, finish);
  const currentTimeRef = useRef(player.currentTime);
  const lastPlayRequest = useRef(playRequest);
  const lastReplayRequest = useRef(replayRequest);
  const lastPauseRequest = useRef(pauseRequest);
  const lastTargetKey = useRef<string | undefined>(undefined);
  const pendingTargetPlay = useRef(false);
  currentTimeRef.current = player.currentTime;

  useEffect(() => {
    onPlayingChange(player.isPlaying);
  }, [onPlayingChange, player.isPlaying]);

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
      pendingTargetPlay.current = !!target && autoPlay;
      lastTargetKey.current = targetKey;
    }
  }, [autoPlay, target?.url, targetKey]);

  const playFrom = useCallback(async (offset?: number) => {
    if (!target || !activeUrl || !player.audioBuffer) return;
    try {
      await player.playRange({
        start: 0,
        end: player.audioBuffer.duration,
        offset: offset ?? (currentTimeRef.current >= player.audioBuffer.duration ? 0 : currentTimeRef.current),
        segmentId: `${target.entry.entry_id}:${target.phase}:${target.sequenceOccurrenceId || "direct"}`,
      });
    } catch {
      setError("Audio could not be played.");
    }
  }, [activeUrl, player.audioBuffer, player.playRange, target]);

  // Clicking the wave while paused (including the configured silence between
  // word and sentence) starts playback from that point. While already
  // playing, the range input's change event has already restarted the source
  // at the new offset, so the pointer-up only has work to do when paused.
  // The pending gap timer must be cancelled first, or it could fire mid-clip
  // and advance the sequence while the clicked audio is still running.
  const handleWaveSeekPlay = useCallback((time: number) => {
    if (player.isPlaying) return;
    onCancelSilence();
    void playFrom(time);
  }, [onCancelSilence, playFrom, player.isPlaying]);

  // A newly selected target starts only when visible-list playback is active.
  // Keep this request pending until the new buffer has decoded; otherwise a
  // fast navigation can increment playRequest before the target is ready and
  // silently lose the autoplay request (most noticeable in Single mode).
  useEffect(() => {
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
    // A navigation request may have already been observed by the effect
    // below while the new buffer was decoding.  Mark it handled here so the
    // ready-buffer transition starts the clip exactly once.
    lastPlayRequest.current = playRequest;
    void playFrom(0);
  }, [activeUrl, autoPlay, playFrom, playRequest, player.audioBuffer, player.isPlaying, player.loadedAudioUrl, target?.url, targetKey]);

  useEffect(() => {
    if (playRequest === lastPlayRequest.current) return;
    lastPlayRequest.current = playRequest;
    if (autoPlay && activeUrl === target?.url && player.loadedAudioUrl === activeUrl && player.audioBuffer) void playFrom();
  }, [activeUrl, autoPlay, playFrom, playRequest, player.audioBuffer, player.loadedAudioUrl, target?.url]);

  useEffect(() => {
    if (replayRequest === lastReplayRequest.current) return;
    lastReplayRequest.current = replayRequest;
    if (player.audioBuffer) {
      player.setPosition(0);
      void playFrom(0);
    }
  }, [playFrom, player.audioBuffer, player.setPosition, replayRequest]);

  useEffect(() => {
    if (pauseRequest === lastPauseRequest.current) return;
    lastPauseRequest.current = pauseRequest;
    player.pause();
  }, [pauseRequest, player.pause]);

  const duration = player.audioBuffer?.duration || 0;
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

  return (
    <section className="react-player" aria-label="Playback controls">
      <div className="react-player-wave-row">
        <button type="button" className="react-player-primary" onClick={onTogglePlayback} disabled={!player.audioBuffer} aria-keyshortcuts="Space" aria-label={isPlaybackActive ? "Pause" : "Play"} title={`${isPlaybackActive ? "Pause" : "Play"} (Space)`}>
          {isPlaybackActive ? <Pause size={24} weight="fill" /> : <Play size={24} weight="fill" />}
        </button>
        <LineWaveform
          audioBuffer={player.audioBuffer}
          loadFailed={player.loadFailed}
          start={0}
          end={duration || 0.01}
          currentTime={player.currentTime}
          silenceGaps={silenceGaps}
          vadNonSpeechIntervals={[]}
          onSeek={(time) => void player.seek(time)}
          onSeekPlay={handleWaveSeekPlay}
          onNavigationPointsChange={() => {}}
        />
      </div>
      <div className="react-player-controls">
        <button type="button" onClick={onPrevious} disabled={!canPrevious} aria-label="Play previous word or sentence" title="Previous (A / ←)"><SkipBack size={18} weight="fill" /></button>
        <button type="button" onClick={onReplay} disabled={!player.audioBuffer} aria-label="Replay focused word or sentence" title="Replay (R)"><ArrowCounterClockwise size={18} weight="bold" /></button>
        <button type="button" onClick={onNext} disabled={!canNext} aria-label="Play next word or sentence" title="Next (D / →)"><SkipForward size={18} weight="fill" /></button>
        <button
          type="button"
          className={playbackRunMode === "consecutive" ? "is-selected" : ""}
          onClick={onTogglePlaybackRunMode}
          aria-pressed={playbackRunMode === "consecutive"}
          aria-label={playbackRunMode === "single" ? "Switch to consecutive playback" : "Switch to single clip playback"}
          title={playbackRunMode === "single" ? "Switch to consecutive playback" : "Switch to single clip playback"}
        >
          {playbackRunMode === "consecutive" ? <Repeat size={18} weight="bold" /> : <RepeatOnce size={18} weight="bold" />}
        </button>
        <span className="react-player-controls-sep" aria-hidden="true" />
        <button type="button" className={`mark-known${markStatus === "known" ? " is-on" : ""}`} onClick={() => void onToggleMark("known")} disabled={!target} aria-label="Mark as known" title="Mark as known" aria-pressed={markStatus === "known"}>✓</button>
        <button type="button" className={`mark-flagged${markStatus === "flagged" ? " is-on" : ""}`} onClick={() => void onToggleMark("flagged")} disabled={!target} aria-label="Flag for review" title="Flag for review" aria-pressed={markStatus === "flagged"}>⚑</button>
        <span className="react-player-status">{error || `${playbackRunMode === "single" ? "Single clip" : "Play through list"} · Click the wave to seek or play · Space to play/pause`}</span>
      </div>
    </section>
  );
}
