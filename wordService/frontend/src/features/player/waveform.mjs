export const PAUSE_DETECTION_DEFAULTS = Object.freeze({
  frameMs: 10,
  minimumPauseMs: 120,
  silenceBelowSpeechDb: 18,
});

function percentile(values, quantile) {
  if (!values.length) return 0;
  const sorted = [...values].sort((left, right) => left - right);
  const index = Math.min(sorted.length - 1, Math.max(0, Math.floor((sorted.length - 1) * quantile)));
  return sorted[index];
}

export function detectPauseCentersMs(
  channels,
  sampleRate,
  startMs,
  endMs,
  options = PAUSE_DETECTION_DEFAULTS,
) {
  return detectSilenceRunsMs(channels, sampleRate, startMs, endMs, options)
    .map(({startMs: runStartMs, endMs: runEndMs}) => (runStartMs + runEndMs) / 2);
}

// Keep the exact same adaptive detector available as intervals for the
// waveform overlay. The audio itself remains the timing authority; these
// intervals are visual review evidence derived from the decoded PCM.
export function detectSilenceGapsMs(
  channels,
  sampleRate,
  startMs,
  endMs,
  options = PAUSE_DETECTION_DEFAULTS,
) {
  return detectSilenceRunsMs(channels, sampleRate, startMs, endMs, options);
}

function detectSilenceRunsMs(
  channels,
  sampleRate,
  startMs,
  endMs,
  options,
) {
  if (!channels.length || !Number.isFinite(sampleRate) || sampleRate <= 0) return [];

  const availableFrames = Math.min(...channels.map((channel) => channel.length));
  if (!Number.isFinite(availableFrames) || availableFrames <= 0) return [];

  const frameMs = Math.max(1, options.frameMs || PAUSE_DETECTION_DEFAULTS.frameMs);
  const minimumPauseMs = Math.max(
    frameMs,
    options.minimumPauseMs || PAUSE_DETECTION_DEFAULTS.minimumPauseMs,
  );
  const silenceBelowSpeechDb = Math.max(
    1,
    options.silenceBelowSpeechDb || PAUSE_DETECTION_DEFAULTS.silenceBelowSpeechDb,
  );
  const startFrame = Math.min(
    availableFrames - 1,
    Math.max(0, Math.floor((Math.max(0, startMs) / 1000) * sampleRate)),
  );
  const endFrame = Math.min(
    availableFrames,
    Math.max(startFrame + 1, Math.ceil((Math.max(startMs, endMs) / 1000) * sampleRate)),
  );
  const framesPerWindow = Math.max(1, Math.round((sampleRate * frameMs) / 1000));
  const rmsValues = [];

  for (let windowStart = startFrame; windowStart < endFrame; windowStart += framesPerWindow) {
    const windowEnd = Math.min(endFrame, windowStart + framesPerWindow);
    let sumSquares = 0;
    let sampleCount = 0;

    for (let frame = windowStart; frame < windowEnd; frame += 1) {
      for (const channel of channels) {
        const sample = channel[frame] || 0;
        sumSquares += sample * sample;
        sampleCount += 1;
      }
    }
    rmsValues.push(Math.sqrt(sumSquares / Math.max(1, sampleCount)));
  }

  const speechLevel = percentile(rmsValues, 0.85);
  if (speechLevel <= 0.00001) return [];

  // The relative threshold adapts to each sentence. The noise-floor term keeps
  // low-level room noise from preventing a real spoken pause from being found.
  const noiseFloor = percentile(rmsValues, 0.15);
  const relativeThreshold = speechLevel * 10 ** (-silenceBelowSpeechDb / 20);
  const silenceThreshold = Math.min(
    speechLevel * 0.45,
    Math.max(relativeThreshold, noiseFloor * 1.5),
  );
  const silenceRuns = [];
  let quietRunStart = -1;

  for (let index = 0; index <= rmsValues.length; index += 1) {
    const isQuiet = index < rmsValues.length && rmsValues[index] <= silenceThreshold;
    if (isQuiet && quietRunStart < 0) quietRunStart = index;
    if (isQuiet || quietRunStart < 0) continue;

    const quietRunEnd = index;
    const quietDurationMs = (quietRunEnd - quietRunStart) * frameMs;
    const isInternalPause = quietRunStart > 0 && quietRunEnd < rmsValues.length;
    if (isInternalPause && quietDurationMs >= minimumPauseMs) {
      const runStartMs = Math.min(endMs, Math.max(startMs, startMs + quietRunStart * frameMs));
      const runEndMs = Math.min(endMs, Math.max(startMs, startMs + quietRunEnd * frameMs));
      silenceRuns.push({startMs: runStartMs, endMs: runEndMs});
    }
    quietRunStart = -1;
  }

  return silenceRuns;
}

export function buildWaveformBars(
  channels,
  sampleRate,
  startMs,
  endMs,
  requestedBarCount = 140,
) {
  const barCount = Math.max(1, Math.floor(requestedBarCount));
  if (!channels.length || !Number.isFinite(sampleRate) || sampleRate <= 0) return [];

  const availableFrames = Math.min(...channels.map((channel) => channel.length));
  if (!Number.isFinite(availableFrames) || availableFrames <= 0) return [];

  // Published line timings are the interaction boundary. Sampling only this
  // interval keeps a short sentence visually spacious even inside a long clip.
  const startFrame = Math.min(
    availableFrames - 1,
    Math.max(0, Math.floor((Math.max(0, startMs) / 1000) * sampleRate)),
  );
  const endFrame = Math.min(
    availableFrames,
    Math.max(startFrame + 1, Math.ceil((Math.max(startMs, endMs) / 1000) * sampleRate)),
  );
  const frameCount = endFrame - startFrame;
  const rawPeaks = [];

  for (let barIndex = 0; barIndex < barCount; barIndex += 1) {
    const bucketStart = startFrame + Math.floor((barIndex * frameCount) / barCount);
    const bucketEnd = Math.max(
      bucketStart + 1,
      startFrame + Math.floor(((barIndex + 1) * frameCount) / barCount),
    );
    let peak = 0;

    for (let frame = bucketStart; frame < Math.min(bucketEnd, endFrame); frame += 1) {
      let mixedAmplitude = 0;
      for (const channel of channels) mixedAmplitude += Math.abs(channel[frame] || 0);
      peak = Math.max(peak, mixedAmplitude / channels.length);
    }
    rawPeaks.push(peak);
  }

  const loudest = Math.max(...rawPeaks, 0.0001);
  return rawPeaks.map((peak) => Math.max(0.07, peak / loudest));
}
