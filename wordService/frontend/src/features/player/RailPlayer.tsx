import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAudioBufferPlayer } from "./useAudioBufferPlayer";
import { LineWaveform } from "./LineWaveform";
import { detectSilenceGapsMs } from "./waveform.mjs";
import type { PlaybackRunMode } from "./playbackSettings";
import type { AudioTarget } from "../../types";

function formatTime(value: number) {
  if (!Number.isFinite(value) || value < 0) return "0:00";
  return `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, "0")}`;
}

interface RailPlayerProps {
  target: AudioTarget | null;
  autoPlay: boolean;
  isPlaybackActive: boolean;
  isSilencePlaying: boolean;
  playbackRunMode: PlaybackRunMode;
  playRequest: number;
  replayRequest: number;
  pauseRequest: number;
  stopRequest: number;
  onEnded: () => void;
  onPlayingChange: (playing: boolean) => void;
  onTogglePlayback: () => void;
  onTogglePlaybackRunMode: () => void;
  onReplay: () => void;
  onPrevious: () => void;
  onNext: () => void;
  onStop: () => void;
  canPrevious: boolean;
  canNext: boolean;
}

export function RailPlayer({
  target,
  autoPlay,
  isPlaybackActive,
  isSilencePlaying,
  playbackRunMode,
  playRequest,
  replayRequest,
  pauseRequest,
  stopRequest,
  onEnded,
  onPlayingChange,
  onTogglePlayback,
  onTogglePlaybackRunMode,
  onReplay,
  onPrevious,
  onNext,
  onStop,
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
  const lastStopRequest = useRef(stopRequest);
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

  useEffect(() => {
    if (stopRequest === lastStopRequest.current) return;
    lastStopRequest.current = stopRequest;
    player.pause();
    player.setPosition(0);
  }, [player.pause, player.setPosition, stopRequest]);

  const duration = player.audioBuffer?.duration || 0;
  const progressLabel = `${formatTime(player.currentTime)} / ${formatTime(duration)}`;
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
      <LineWaveform
        audioBuffer={player.audioBuffer}
        loadFailed={player.loadFailed}
        start={0}
        end={duration || 0.01}
        currentTime={player.currentTime}
        silenceGaps={silenceGaps}
        vadNonSpeechIntervals={[]}
        onSeek={(time) => void player.seek(time)}
        onNavigationPointsChange={() => {}}
      />
      <div className="react-player-controls">
        <span className="audio-time" aria-label="Playback time">{progressLabel}</span>
        <button type="button" onClick={onPrevious} disabled={!canPrevious} aria-label="Play previous word or sentence">Previous</button>
        <button type="button" onClick={onReplay} disabled={!player.audioBuffer} aria-label="Replay focused word or sentence">Replay</button>
        <button type="button" className="react-player-primary" onClick={onTogglePlayback} disabled={!player.audioBuffer} aria-keyshortcuts="Space">
          {isPlaybackActive ? "Pause" : "Play"}
        </button>
        <button type="button" onClick={onNext} disabled={!canNext} aria-label="Play next word or sentence">Next</button>
        <button type="button" onClick={onStop} disabled={!player.audioBuffer} aria-keyshortcuts="Escape">Stop</button>
        <button
          type="button"
          className={playbackRunMode === "consecutive" ? "is-selected" : ""}
          onClick={onTogglePlaybackRunMode}
          aria-pressed={playbackRunMode === "consecutive"}
          aria-label={playbackRunMode === "single" ? "Switch to consecutive playback" : "Switch to single clip playback"}
          title={playbackRunMode === "single" ? "Switch to consecutive playback" : "Switch to single clip playback"}
        >
          {playbackRunMode === "single" ? "Single" : "Consecutive"}
        </button>
        <span className="react-player-shortcuts" aria-label="Keyboard shortcuts">A previous · D next</span>
        <span className="react-player-status">{error || (isSilencePlaying ? `Playing silence after ${target?.phase || "audio"}` : isPlaybackActive ? "Playing focused audio" : `${playbackRunMode === "single" ? "Single clip" : "Play through list"} · Click the wave to seek · Space to play`)}</span>
      </div>
    </section>
  );
}
