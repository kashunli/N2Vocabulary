import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAudioBufferPlayer } from "./useAudioBufferPlayer";
import { LineWaveform } from "./LineWaveform";
import { detectSilenceGapsMs } from "./waveform.mjs";
import type { AudioTarget } from "../../types";

function formatTime(value: number) {
  if (!Number.isFinite(value) || value < 0) return "0:00";
  return `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, "0")}`;
}

interface RailPlayerProps {
  target: AudioTarget | null;
  autoPlay: boolean;
  playRequest: number;
  replayRequest: number;
  pauseRequest: number;
  stopRequest: number;
  onEnded: () => void;
  onPlayingChange: (playing: boolean) => void;
  onTogglePlayback: () => void;
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
  playRequest,
  replayRequest,
  pauseRequest,
  stopRequest,
  onEnded,
  onPlayingChange,
  onTogglePlayback,
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
  currentTimeRef.current = player.currentTime;

  useEffect(() => {
    onPlayingChange(player.isPlaying);
  }, [onPlayingChange, player.isPlaying]);

  useEffect(() => {
    setError("");
    setActiveUrl(target?.url);
  }, [target?.url]);

  const playFrom = useCallback(async (offset?: number) => {
    if (!target || !activeUrl || !player.audioBuffer) return;
    try {
      await player.playRange({
        start: 0,
        end: player.audioBuffer.duration,
        offset: offset ?? (currentTimeRef.current >= player.audioBuffer.duration ? 0 : currentTimeRef.current),
        segmentId: `${target.entry.entry_id}:${target.phase}`,
      });
    } catch {
      setError("Audio could not be played.");
    }
  }, [activeUrl, player.audioBuffer, player.playRange, target]);

  // A newly selected target starts only when visible-list playback is active.
  // Manual controls can still request the same decoded clip explicitly below.
  useEffect(() => {
    if (autoPlay && target && activeUrl && player.audioBuffer && !player.isPlaying && player.currentTime === 0) {
      void playFrom();
    }
  }, [activeUrl, autoPlay, playFrom, player.audioBuffer, player.isPlaying, target]);

  useEffect(() => {
    if (playRequest === lastPlayRequest.current) return;
    lastPlayRequest.current = playRequest;
    if (autoPlay && player.audioBuffer) void playFrom();
  }, [autoPlay, playFrom, playRequest, player.audioBuffer]);

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
      <div className="react-player-heading">
        <div>
          <span className="eyebrow">AUDIO · DECODED TIMELINE</span>
          <strong>{target ? `${target.entry.kanji} · ${target.phase}` : "Select a word or sentence"}</strong>
        </div>
        <span className="audio-time">{progressLabel}</span>
      </div>
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
        <button type="button" onClick={onPrevious} disabled={!canPrevious} aria-label="Play previous word or sentence">Previous</button>
        <button type="button" onClick={onReplay} disabled={!player.audioBuffer} aria-label="Replay focused word or sentence">Replay</button>
        <button type="button" className="react-player-primary" onClick={onTogglePlayback} disabled={!player.audioBuffer} aria-keyshortcuts="Space">
          {player.isPlaying ? "Pause" : "Play"}
        </button>
        <button type="button" onClick={onNext} disabled={!canNext} aria-label="Play next word or sentence">Next</button>
        <button type="button" onClick={onStop} disabled={!player.audioBuffer} aria-keyshortcuts="Escape">Stop</button>
        <span className="react-player-status">{error || (player.isPlaying ? "Playing focused audio" : "Click the wave to seek · Space to play")}</span>
      </div>
    </section>
  );
}
