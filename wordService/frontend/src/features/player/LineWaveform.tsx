import { useCallback, useEffect, useId, useMemo, useRef } from "react";

import { useI18n } from "../../i18n";
import { formatTime } from "./playerState.mjs";
import {
  buildWaveformBars,
  detectPauseCentersMs,
} from "./waveform.mjs";

interface LineWaveformProps {
  audioBuffer: AudioBuffer | null;
  loadFailed: boolean;
  start: number;
  end: number;
  currentTime: number;
  smoothPlayback?: boolean;
  silenceGaps: { start_ms: number; end_ms: number }[];
  vadNonSpeechIntervals: { start_ms: number; end_ms: number }[];
  onSeek: (time: number) => void;
  onSeekPlay?: (time: number) => void;
  onNavigationPointsChange: (start: number, end: number, points: number[]) => void;
}

const BAR_COUNT = 148;

export function LineWaveform({
  audioBuffer,
  loadFailed,
  start,
  end,
  currentTime,
  smoothPlayback = false,
  silenceGaps,
  vadNonSpeechIntervals,
  onSeek,
  onSeekPlay,
  onNavigationPointsChange,
}: LineWaveformProps) {
  const {copy} = useI18n();
  const clipId = "waveform-progress-" + useId().replace(/:/g, "");
  const safeStart = Number.isFinite(start) ? Math.max(0, start) : 0;
  const safeEnd = Number.isFinite(end) ? Math.max(safeStart + 0.01, end) : safeStart + 0.01;
  const safeCurrent = Math.min(safeEnd, Math.max(safeStart, currentTime));
  const lineDuration = safeEnd - safeStart;
  const progress = (safeCurrent - safeStart) / lineDuration;
  const waveformProgressRef = useRef<SVGRectElement | null>(null);
  const waveformCursorRef = useRef<SVGLineElement | null>(null);
  const visualAnchorTimeRef = useRef(safeCurrent);
  const visualAnchorWallTimeRef = useRef(0);

  const applyVisualTime = useCallback((time: number) => {
    const safeTime = Math.min(safeEnd, Math.max(safeStart, time));
    const visualProgress = (safeTime - safeStart) / lineDuration;
    const x = visualProgress * 1000;
    waveformProgressRef.current?.setAttribute("width", String(x));
    waveformCursorRef.current?.setAttribute("x1", String(x));
    waveformCursorRef.current?.setAttribute("x2", String(x));
  }, [lineDuration, safeEnd, safeStart]);

  // Native Android playback reports a coarse position heartbeat so that the
  // bridge remains cheap while the screen is locked. Once the screen is
  // visible, interpolate between heartbeats on the browser's animation frame
  // clock; this keeps the visual cursor smooth without retaining 60 bridge
  // events per second or rerendering the entire study wall.
  useEffect(() => {
    visualAnchorTimeRef.current = safeCurrent;
    visualAnchorWallTimeRef.current = performance.now();
    applyVisualTime(safeCurrent);
  }, [applyVisualTime, safeCurrent, smoothPlayback]);

  useEffect(() => {
    if (!smoothPlayback) return undefined;
    let frame: number | null = null;
    const update = (now: number) => {
      const elapsed = Math.max(0, (now - visualAnchorWallTimeRef.current) / 1000);
      const nextTime = visualAnchorTimeRef.current + elapsed;
      applyVisualTime(nextTime);
      if (nextTime < safeEnd) {
        frame = requestAnimationFrame(update);
      } else {
        frame = null;
      }
    };
    frame = requestAnimationFrame(update);
    return () => {
      if (frame !== null) cancelAnimationFrame(frame);
    };
  }, [applyVisualTime, safeEnd, smoothPlayback]);

  const bars = useMemo(() => {
    if (!audioBuffer) return [];
    const channels = Array.from(
      { length: audioBuffer.numberOfChannels },
      (_, index) => audioBuffer.getChannelData(index),
    );
    return buildWaveformBars(
      channels,
      audioBuffer.sampleRate,
      safeStart * 1000,
      safeEnd * 1000,
      BAR_COUNT,
    );
  }, [audioBuffer, safeStart, safeEnd]);

  const navigationPoints = useMemo(() => {
    if (!audioBuffer) return [];
    const channels = Array.from(
      { length: audioBuffer.numberOfChannels },
      (_, index) => audioBuffer.getChannelData(index),
    );
    const internalPauses = detectPauseCentersMs(
      channels,
      audioBuffer.sampleRate,
      safeStart * 1000,
      safeEnd * 1000,
    )
      .map((pauseMs) => pauseMs / 1000)
      .filter((pause) => pause > safeStart + 0.04 && pause < safeEnd - 0.04);
    return [safeStart, ...internalPauses, safeEnd];
  }, [audioBuffer, safeStart, safeEnd]);

  useEffect(() => {
    onNavigationPointsChange(safeStart, safeEnd, navigationPoints);
  }, [navigationPoints, onNavigationPointsChange, safeEnd, safeStart]);

  const displayedBars = bars.length ? bars : Array.from({ length: BAR_COUNT }, () => 0.07);
  const gap = 2.1;
  const barWidth = (1000 - gap * (displayedBars.length - 1)) / displayedBars.length;
  const barElements = displayedBars.map((height, index) => {
    const renderedHeight = Math.max(5, height * 84);
    return (
      <rect
        key={index}
        x={index * (barWidth + gap)}
        y={(100 - renderedHeight) / 2}
        width={barWidth}
        height={renderedHeight}
        rx={Math.min(2, barWidth / 2)}
      />
    );
  });
  const silenceElements = silenceGaps.map((gap, index) => {
    const startMs = Math.max(safeStart * 1000, gap.start_ms);
    const endMs = Math.min(safeEnd * 1000, gap.end_ms);
    if (endMs <= startMs) return null;
    return <rect key={index} className="waveform-silence-gap" x={((startMs / 1000 - safeStart) / lineDuration) * 1000} y="2" width={((endMs - startMs) / 1000 / lineDuration) * 1000} height="96" rx="3" />;
  });
  const vadSilenceElements = vadNonSpeechIntervals.map((interval, index) => {
    const startMs = Math.max(safeStart * 1000, interval.start_ms);
    const endMs = Math.min(safeEnd * 1000, interval.end_ms);
    if (endMs <= startMs) return null;
    return <rect key={index} className="waveform-vad-silence" x={((startMs / 1000 - safeStart) / lineDuration) * 1000} y="2" width={((endMs - startMs) / 1000 / lineDuration) * 1000} height="96" rx="3" />;
  });

  return (
    <div className={"line-waveform" + (bars.length ? " is-ready" : " is-loading")}>
      <svg viewBox="0 0 1000 100" preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <clipPath id={clipId}>
            <rect ref={waveformProgressRef} x="0" y="0" width={progress * 1000} height="100" />
          </clipPath>
        </defs>
        <g className="waveform-silence-gaps">{silenceElements}</g>
        <g className="waveform-vad-silence-gaps">{vadSilenceElements}</g>
        <g className="waveform-unplayed">{barElements}</g>
        <g className="waveform-played" clipPath={`url(#${clipId})`}>{barElements}</g>
        <line ref={waveformCursorRef} className="waveform-cursor" x1={progress * 1000} x2={progress * 1000} y1="4" y2="96" />
      </svg>
      <input
        type="range"
        min={safeStart}
        max={safeEnd}
        step="0.01"
        value={safeCurrent}
        onChange={(event) => onSeek(Number(event.target.value))}
        onPointerUp={(event) => onSeekPlay?.(Number(event.currentTarget.value))}
        aria-label={copy.player.waveformPosition}
        aria-valuetext={`${formatTime(safeCurrent - safeStart)} / ${formatTime(lineDuration)}`}
      />
      {loadFailed ? <span className="sr-only">{copy.player.waveformLoadFailed}</span> : null}
    </div>
  );
}
