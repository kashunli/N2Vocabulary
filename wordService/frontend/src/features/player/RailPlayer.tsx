import { useCallback, useEffect, useMemo, useState } from "react";

import { useAudioBufferPlayer } from "./useAudioBufferPlayer";
import { LineWaveform } from "./LineWaveform";
import type { AudioTarget } from "../../types";

function formatTime(value: number) {
  if (!Number.isFinite(value) || value < 0) return "0:00";
  return `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, "0")}`;
}

export function RailPlayer({target, onEnded}: {target: AudioTarget | null; onEnded: () => void}) {
  const [activeUrl, setActiveUrl] = useState<string>();
  const [error, setError] = useState("");
  const finish = useCallback(() => onEnded(), [onEnded]);
  const player = useAudioBufferPlayer(activeUrl, finish);

  useEffect(() => {
    setError("");
    setActiveUrl(target?.url);
  }, [target?.url]);

  const play = useCallback(async () => {
    if (!target || !activeUrl || !player.audioBuffer) return;
    try {
      await player.playRange({
        start: 0,
        end: player.audioBuffer.duration,
        offset: player.currentTime >= player.audioBuffer.duration ? 0 : player.currentTime,
        segmentId: `${target.entry.entry_id}:${target.phase}`,
      });
    } catch {
      setError("Audio could not be played.");
    }
  }, [activeUrl, player, target]);

  useEffect(() => {
    if (target && activeUrl && player.audioBuffer && !player.isPlaying && player.currentTime === 0) {
      void play();
    }
  }, [activeUrl, play, player.audioBuffer, player.currentTime, player.isPlaying, target]);

  const stop = useCallback(() => player.pause(), [player]);
  const toggle = useCallback(() => {
    if (player.isPlaying) stop();
    else void play();
  }, [play, player.isPlaying, stop]);

  const duration = player.audioBuffer?.duration || 0;
  const progressLabel = `${formatTime(player.currentTime)} / ${formatTime(duration)}`;
  const gaps = useMemo(() => [], []);

  return (
    <section className="react-player" aria-label="Current audio player">
      <div className="react-player-heading">
        <div>
          <span className="eyebrow">AUDIO · REACT PREVIEW</span>
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
        silenceGaps={gaps}
        vadNonSpeechIntervals={[]}
        onSeek={(time) => void player.seek(time)}
        onNavigationPointsChange={() => {}}
      />
      <div className="react-player-controls">
        <button type="button" onClick={toggle} disabled={!player.audioBuffer}>{player.isPlaying ? "Pause" : "Play"}</button>
        <button type="button" onClick={() => { player.setPosition(0); void play(); }} disabled={!player.audioBuffer}>Replay</button>
        <span>{error || "Decoded audio and waveform share one timeline."}</span>
      </div>
    </section>
  );
}
