// Keep this payload contract in sync with frontend/src/features/study/studyFocus.ts.
export const STUDY_FOCUS_STORAGE_KEY = "n2-word-service:study-focus:v1";

function normalizeFocus(value) {
  if (!value || typeof value !== "object") return null;
  const bookCode = typeof value.bookCode === "string" ? value.bookCode.trim().toUpperCase() : "";
  const entryId = Number(value.entryId);
  if (!bookCode || !Number.isInteger(entryId) || entryId <= 0) return null;

  const unitValue = Number(value.unitNumber);
  return {
    bookCode,
    entryId,
    phase: value.phase === "sentence" ? "sentence" : "word",
    ...(Number.isInteger(unitValue) && unitValue > 0 ? {unitNumber: unitValue} : {}),
    updatedAt: Number.isFinite(Number(value.updatedAt)) ? Number(value.updatedAt) : 0,
  };
}

export function readStudyFocus() {
  try {
    const raw = window.localStorage.getItem(STUDY_FOCUS_STORAGE_KEY);
    return raw ? normalizeFocus(JSON.parse(raw)) : null;
  } catch {
    return null;
  }
}

export function saveStudyFocus(focus) {
  const normalized = normalizeFocus(focus);
  if (!normalized) return;
  try {
    window.localStorage.setItem(STUDY_FOCUS_STORAGE_KEY, JSON.stringify({
      ...normalized,
      updatedAt: Date.now(),
    }));
  } catch (error) {
    console.warn("Could not save shared study focus", error);
  }
}
