import { elements, state } from "./state.js";

let railWavebarCleanup = null;
let railWavebarAudioContext = null;
let railWavebarLoadToken = 0;
let railWavebarAnimationFrame = null;
const railWaveformCache = new Map();
const RAIL_WAVE_BAR_COUNT = 148;

function formatRailWaveTime(value) {
  if (!Number.isFinite(value) || value < 0) return "0:00";
  const minutes = Math.floor(value / 60);
  const seconds = Math.floor(value % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function placeholderRailWaveform(seed) {
  let hash = 17;
  for (const character of String(seed || "clip")) hash = (hash * 31 + character.charCodeAt(0)) % 997;
  return Array.from({length: RAIL_WAVE_BAR_COUNT}, (_, index) => {
    const wave = Math.abs(Math.sin((index + 1) * 0.73 + hash * 0.017));
    return Math.max(0.07, 0.22 + wave * 0.68);
  });
}

function waveformValuesFromBuffer(audioBuffer) {
  const channels = Array.from(
    {length: audioBuffer.numberOfChannels},
    (_, index) => audioBuffer.getChannelData(index),
  );
  const rawPeaks = [];
  for (let barIndex = 0; barIndex < RAIL_WAVE_BAR_COUNT; barIndex += 1) {
    const start = Math.floor((barIndex * audioBuffer.length) / RAIL_WAVE_BAR_COUNT);
    const end = Math.max(start + 1, Math.floor(((barIndex + 1) * audioBuffer.length) / RAIL_WAVE_BAR_COUNT));
    let peak = 0;
    for (let frame = start; frame < Math.min(end, audioBuffer.length); frame += 1) {
      let amplitude = 0;
      for (const channel of channels) amplitude += Math.abs(channel[frame] || 0);
      peak = Math.max(peak, amplitude / Math.max(1, channels.length));
    }
    rawPeaks.push(peak);
  }
  const loudest = Math.max(...rawPeaks, 0.0001);
  return rawPeaks.map(peak => Math.max(0.07, peak / loudest));
}

function percentile(values, quantile) {
  if (!values.length) return 0;
  const sorted = [...values].sort((left, right) => left - right);
  return sorted[Math.min(sorted.length - 1, Math.max(0, Math.floor((sorted.length - 1) * quantile)))];
}

function detectRailSilenceGaps(audioBuffer) {
  const channels = Array.from(
    {length: audioBuffer.numberOfChannels},
    (_, index) => audioBuffer.getChannelData(index),
  );
  const frameMs = 10;
  const framesPerWindow = Math.max(1, Math.round(audioBuffer.sampleRate * frameMs / 1000));
  const rmsValues = [];
  for (let start = 0; start < audioBuffer.length; start += framesPerWindow) {
    const end = Math.min(audioBuffer.length, start + framesPerWindow);
    let sumSquares = 0;
    let sampleCount = 0;
    for (let frame = start; frame < end; frame += 1) {
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
  const noiseFloor = percentile(rmsValues, 0.15);
  const relativeThreshold = speechLevel * 10 ** (-18 / 20);
  const threshold = Math.min(speechLevel * 0.45, Math.max(relativeThreshold, noiseFloor * 1.5));
  const gaps = [];
  let quietStart = -1;
  for (let index = 0; index <= rmsValues.length; index += 1) {
    const quiet = index < rmsValues.length && rmsValues[index] <= threshold;
    if (quiet && quietStart < 0) quietStart = index;
    if (quiet || quietStart < 0) continue;
    const quietEnd = index;
    if (quietStart > 0 && quietEnd < rmsValues.length && (quietEnd - quietStart) * frameMs >= 120) {
      gaps.push({
        start: quietStart / rmsValues.length,
        end: quietEnd / rmsValues.length,
      });
    }
    quietStart = -1;
  }
  return gaps;
}

function renderRailWavebarSilence(gaps) {
  if (!elements.railWavebarSilence) return;
  elements.railWavebarSilence.innerHTML = gaps.map(gap => (
    `<rect class="rail-wavebar-silence-gap" x="${gap.start * 1000}" y="2" width="${(gap.end - gap.start) * 1000}" height="96" rx="3"></rect>`
  )).join("");
}

function renderRailWavebarBars(values, gaps = []) {
  const unplayed = elements.railWavebarUnplayed;
  const played = elements.railWavebarPlayed;
  if (!unplayed || !played) return;
  const gap = 2.1;
  const barWidth = (1000 - gap * (values.length - 1)) / values.length;
  const rects = values.map((height, index) => {
    const renderedHeight = Math.max(5, height * 84);
    const x = index * (barWidth + gap);
    const y = (100 - renderedHeight) / 2;
    return `<rect x="${x}" y="${y}" width="${barWidth}" height="${renderedHeight}" rx="${Math.min(2, barWidth / 2)}"></rect>`;
  }).join("");
  unplayed.innerHTML = rects;
  played.innerHTML = rects;
  renderRailWavebarSilence(gaps);
}

async function loadRailWaveform(audio, seed, token) {
  const src = audio.currentSrc || audio.src;
  if (!src || token !== railWavebarLoadToken) return;
  if (railWaveformCache.has(src)) {
    const cached = railWaveformCache.get(src);
    renderRailWavebarBars(cached.values, cached.gaps);
    syncRailWavebar(audio);
    return;
  }
  try {
    if (!railWavebarAudioContext) {
      const AudioContextConstructor = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextConstructor) return;
      railWavebarAudioContext = new AudioContextConstructor();
    }
    const response = await fetch(src);
    if (!response.ok) throw new Error(`Waveform audio request failed: ${response.status}`);
    const audioBuffer = await railWavebarAudioContext.decodeAudioData(await response.arrayBuffer());
    const values = waveformValuesFromBuffer(audioBuffer);
    const gaps = detectRailSilenceGaps(audioBuffer);
    railWaveformCache.set(src, {values, gaps});
    if (token === railWavebarLoadToken && state.currentAudio === audio) {
      renderRailWavebarBars(values, gaps);
      syncRailWavebar(audio);
    }
  } catch (error) {
    // Keep the deterministic placeholder if a browser cannot decode this clip.
    if (token === railWavebarLoadToken) renderRailWavebarBars(placeholderRailWaveform(seed), []);
  }
}

function syncRailWavebar(audio) {
  if (!elements.railWavebar || !audio) return;
  const duration = Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration : 0;
  const current = duration ? Math.min(duration, Math.max(0, audio.currentTime || 0)) : 0;
  const progress = duration ? current / duration : 0;
  elements.railWavebar.style.setProperty("--wave-progress", String(progress));
  if (elements.railWavebarProgressRect) elements.railWavebarProgressRect.setAttribute("width", String(progress * 1000));
  if (elements.railWavebarCursor) {
    elements.railWavebarCursor.setAttribute("x1", String(progress * 1000));
    elements.railWavebarCursor.setAttribute("x2", String(progress * 1000));
  }
  if (elements.railWavebarSeek) {
    elements.railWavebarSeek.disabled = !duration;
    // Use the actual audio timestamp for the native range control.  This is
    // the same interaction model as Listening Practice: the browser owns the
    // click-and-drag gesture, and each input event seeks to that exact second.
    elements.railWavebarSeek.min = "0";
    elements.railWavebarSeek.max = String(duration || 0);
    elements.railWavebarSeek.step = "0.01";
    elements.railWavebarSeek.value = String(current);
    elements.railWavebarSeek.setAttribute(
      "aria-valuetext",
      `${formatRailWaveTime(current)} / ${formatRailWaveTime(duration)}`,
    );
  }
  if (elements.railWavebarCurrent) elements.railWavebarCurrent.textContent = formatRailWaveTime(current);
  if (elements.railWavebarDuration) elements.railWavebarDuration.textContent = formatRailWaveTime(duration);
}

function stopRailWavebarAnimation() {
  if (railWavebarAnimationFrame === null) return;
  window.cancelAnimationFrame(railWavebarAnimationFrame);
  railWavebarAnimationFrame = null;
}

function animateRailWavebar(audio) {
  stopRailWavebarAnimation();
  const frame = () => {
    if (state.currentAudio !== audio || audio.paused || audio.ended) {
      railWavebarAnimationFrame = null;
      return;
    }
    // Native `timeupdate` is deliberately throttled by browsers. Reading the
    // media clock on each frame keeps the cursor moving like Listening
    // Practice rather than hopping several times per second.
    syncRailWavebar(audio);
    railWavebarAnimationFrame = window.requestAnimationFrame(frame);
  };
  railWavebarAnimationFrame = window.requestAnimationFrame(frame);
}

export function releaseRailWavebar(audio) {
  if (audio && audio._railWavebarCleanup) audio._railWavebarCleanup();
  if (audio && state.currentAudio !== audio) return;
  railWavebarLoadToken += 1;
  stopRailWavebarAnimation();
  railWavebarCleanup?.();
  railWavebarCleanup = null;
  if (elements.railWavebar) elements.railWavebar.style.setProperty("--wave-progress", "0");
  if (elements.railWavebarSeek) {
    elements.railWavebarSeek.disabled = true;
    elements.railWavebarSeek.min = "0";
    elements.railWavebarSeek.max = "0";
    elements.railWavebarSeek.step = "0.01";
    elements.railWavebarSeek.value = "0";
  }
  if (elements.railWavebarLabel) elements.railWavebarLabel.textContent = "Waiting for a clip";
}

export function connectRailWavebar(audio, label, seed) {
  releaseRailWavebar();
  if (!elements.railWavebar) return;
  const loadToken = railWavebarLoadToken;
  renderRailWavebarBars(placeholderRailWaveform(seed), []);
  if (elements.railWavebarLabel) elements.railWavebarLabel.textContent = label;
  const sync = () => syncRailWavebar(audio);
  const startAnimation = () => {
    sync();
    animateRailWavebar(audio);
  };
  const stopAnimation = () => {
    sync();
    stopRailWavebarAnimation();
  };
  ["loadedmetadata", "durationchange", "timeupdate", "play", "pause", "ended"].forEach(event => {
    audio.addEventListener(event, sync);
  });
  audio.addEventListener("play", startAnimation);
  audio.addEventListener("pause", stopAnimation);
  audio.addEventListener("ended", stopAnimation);
  railWavebarCleanup = () => {
    ["loadedmetadata", "durationchange", "timeupdate", "play", "pause", "ended"].forEach(event => {
      audio.removeEventListener(event, sync);
    });
    audio.removeEventListener("play", startAnimation);
    audio.removeEventListener("pause", stopAnimation);
    audio.removeEventListener("ended", stopAnimation);
    stopRailWavebarAnimation();
  };
  audio._railWavebarCleanup = railWavebarCleanup;
  sync();
  loadRailWaveform(audio, seed, loadToken);
}

export function seekRailWavebar(seconds) {
  const audio = state.currentAudio;
  if (!audio || !Number.isFinite(audio.duration) || audio.duration <= 0) return;
  const safeSeconds = Math.min(audio.duration, Math.max(0, Number(seconds) || 0));
  // Assigning `currentTime` seeks asynchronously for compressed audio. Do
  // not redraw from the stale media clock here: wait until the browser has
  // accepted the new position, otherwise a click visibly snaps back.
  audio.addEventListener("seeked", () => syncRailWavebar(audio), {once: true});
  audio.currentTime = safeSeconds;
}

if (elements.railWavebar) renderRailWavebarBars(placeholderRailWaveform("idle"), []);
