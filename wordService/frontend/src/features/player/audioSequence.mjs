export const AUDIO_SEQUENCE_VERSION = 1;
export const MAX_AUDIO_SEQUENCE_STEPS = 12;
export const DEFAULT_SEQUENCE_REPEAT_COUNT = 1;
export const DEFAULT_SEQUENCE_PAUSE_MS = 500;

function clampNumber(value, minimum, maximum, fallback) {
  const number = Number(value);
  if (!Number.isFinite(number)) return fallback;
  return Math.min(maximum, Math.max(minimum, number));
}

function normalizedId(value, fallback) {
  const id = typeof value === "string" ? value.trim() : "";
  return id || fallback;
}

function uniqueStepId(candidate, usedIds, index) {
  const base = normalizedId(candidate, `step-${index + 1}`);
  let id = base;
  let suffix = 2;
  while (usedIds.has(id)) {
    id = `${base}-${suffix}`;
    suffix += 1;
  }
  usedIds.add(id);
  return id;
}

function normalizedElement(value) {
  return value === "sentence" ? "sentence" : "word";
}

function normalizedRepeatCount(value, fallback = DEFAULT_SEQUENCE_REPEAT_COUNT) {
  return Math.round(clampNumber(value, 0, 9, fallback));
}

function normalizedPauseMs(value, fallback = DEFAULT_SEQUENCE_PAUSE_MS) {
  return Math.round(clampNumber(value, 0, 3000, fallback) / 100) * 100;
}

export function createDefaultAudioSequence(
  postWordSilenceMs = DEFAULT_SEQUENCE_PAUSE_MS,
  postSentenceSilenceMs = DEFAULT_SEQUENCE_PAUSE_MS,
) {
  return {
    version: AUDIO_SEQUENCE_VERSION,
    steps: [
      {
        id: "word-1",
        element: "word",
        repeatCount: DEFAULT_SEQUENCE_REPEAT_COUNT,
        pauseAfterMs: normalizedPauseMs(postWordSilenceMs),
      },
      {
        id: "sentence-1",
        element: "sentence",
        repeatCount: DEFAULT_SEQUENCE_REPEAT_COUNT,
        pauseAfterMs: normalizedPauseMs(postSentenceSilenceMs),
      },
    ],
  };
}

export function normalizeAudioSequence(
  value,
  postWordSilenceMs = DEFAULT_SEQUENCE_PAUSE_MS,
  postSentenceSilenceMs = DEFAULT_SEQUENCE_PAUSE_MS,
) {
  const rawSteps = value && typeof value === "object" && Array.isArray(value.steps)
    ? value.steps
    : null;
  if (!rawSteps?.length) {
    return createDefaultAudioSequence(postWordSilenceMs, postSentenceSilenceMs);
  }

  const usedIds = new Set();
  const steps = rawSteps.slice(0, MAX_AUDIO_SEQUENCE_STEPS).map((rawStep, index) => {
    const raw = rawStep && typeof rawStep === "object" ? rawStep : {};
    const element = normalizedElement(raw.element);
    const pauseFallback = element === "word" ? postWordSilenceMs : postSentenceSilenceMs;
    return {
      id: uniqueStepId(raw.id, usedIds, index),
      element,
      repeatCount: normalizedRepeatCount(raw.repeatCount),
      pauseAfterMs: normalizedPauseMs(raw.pauseAfterMs, pauseFallback),
    };
  });

  return {
    version: AUDIO_SEQUENCE_VERSION,
    steps: steps.length ? steps : createDefaultAudioSequence(postWordSilenceMs, postSentenceSilenceMs).steps,
  };
}

export function addAudioSequenceStep(steps, element, pauseAfterMs = DEFAULT_SEQUENCE_PAUSE_MS) {
  if (steps.length >= MAX_AUDIO_SEQUENCE_STEPS) return steps;
  const safeElement = normalizedElement(element);
  const sameElementCount = steps.filter((step) => step.element === safeElement).length + 1;
  const usedIds = new Set(steps.map((step) => step.id));
  const id = uniqueStepId(`${safeElement}-${sameElementCount}`, usedIds, steps.length);
  return [
    ...steps,
    {
      id,
      element: safeElement,
      repeatCount: DEFAULT_SEQUENCE_REPEAT_COUNT,
      pauseAfterMs: normalizedPauseMs(pauseAfterMs),
    },
  ];
}

export function updateAudioSequenceStep(steps, stepId, patch) {
  return steps.map((step) => {
    if (step.id !== stepId) return step;
    const element = normalizedElement(patch?.element ?? step.element);
    return {
      ...step,
      element,
      repeatCount: normalizedRepeatCount(patch?.repeatCount, step.repeatCount),
      pauseAfterMs: normalizedPauseMs(patch?.pauseAfterMs, step.pauseAfterMs),
    };
  });
}

export function removeAudioSequenceStep(steps, stepId) {
  if (steps.length <= 1) return steps;
  return steps.filter((step) => step.id !== stepId);
}

export function moveAudioSequenceStep(steps, stepId, direction) {
  const index = steps.findIndex((step) => step.id === stepId);
  const nextIndex = index + (direction === "up" ? -1 : 1);
  if (index < 0 || nextIndex < 0 || nextIndex >= steps.length) return steps;
  const next = steps.slice();
  [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
  return next;
}

export function materializeAudioSequence(sequence, playbackMode, entry) {
  const steps = Array.isArray(sequence?.steps) ? sequence.steps : [];
  return steps.flatMap((step, sequenceIndex) => {
    if (!step || step.repeatCount <= 0) return [];
    if (playbackMode === "words" && step.element !== "word") return [];
    if (playbackMode === "sentences" && step.element !== "sentence") return [];
    const url = step.element === "word" ? entry?.word_audio_url : entry?.sentence_audio_url;
    if (!url) return [];
    return Array.from({length: step.repeatCount}, (_, repeatIndex) => ({
      ...step,
      phase: step.element,
      sequenceIndex,
      repeatIndex,
      occurrenceId: `${step.id}:${repeatIndex}`,
    }));
  });
}
