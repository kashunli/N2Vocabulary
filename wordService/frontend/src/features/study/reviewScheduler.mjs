export const REVIEW_STATE_VERSION = 1;
export const GOOD_INTERVAL_DAYS = Object.freeze([1, 3, 7, 14, 30, 60]);

const MINUTE_MS = 60 * 1000;
const DAY_MS = 24 * 60 * MINUTE_MS;

function isoAfter(now, milliseconds) {
  const date = new Date(now);
  if (!Number.isFinite(date.getTime())) throw new Error("now must be a valid timestamp");
  return new Date(date.getTime() + milliseconds).toISOString();
}

export function initialDueAt(completedAt) {
  return isoAfter(completedAt, DAY_MS);
}

export function scheduleReview(currentGoodStep, grade, reviewedAt) {
  const step = Math.max(0, Math.min(6, Number.isInteger(currentGoodStep) ? currentGoodStep : 0));
  if (grade === "again") {
    return {goodStep: 0, dueAt: isoAfter(reviewedAt, 10 * MINUTE_MS), setKnown: false, setFlagged: false};
  }
  if (grade === "hard") {
    return {goodStep: step, dueAt: isoAfter(reviewedAt, DAY_MS), setKnown: false, setFlagged: true};
  }
  if (grade === "good") {
    const nextStep = Math.max(1, Math.min(6, step + 1));
    return {
      goodStep: nextStep,
      dueAt: isoAfter(reviewedAt, GOOD_INTERVAL_DAYS[nextStep - 1] * DAY_MS),
      setKnown: true,
      setFlagged: false,
    };
  }
  throw new Error("grade must be again, hard, or good");
}

export function nextGoodIntervalDays(currentGoodStep) {
  const step = Math.max(0, Math.min(6, Number.isInteger(currentGoodStep) ? currentGoodStep : 0));
  return GOOD_INTERVAL_DAYS[Math.max(1, Math.min(6, step + 1)) - 1];
}
