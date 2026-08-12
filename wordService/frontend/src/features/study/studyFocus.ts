export type StudyFocusPhase = "word" | "sentence";

export interface StudyFocus {
  bookCode: string;
  entryId: number;
  phase: StudyFocusPhase;
  unitNumber?: number;
  updatedAt: number;
}

// This key is deliberately shared with the classic wall's studyFocus.js
// module. Keep the payload small and entry-based so a different card layout
// can restore the same learner position without sharing scroll coordinates.
export const STUDY_FOCUS_STORAGE_KEY = "n2-word-service:study-focus:v1";

function normalizeFocus(value: unknown): StudyFocus | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const bookCode = typeof raw.bookCode === "string" ? raw.bookCode.trim().toUpperCase() : "";
  const entryId = Number(raw.entryId);
  if (!bookCode || !Number.isInteger(entryId) || entryId <= 0) return null;

  const phase: StudyFocusPhase = raw.phase === "sentence" ? "sentence" : "word";
  const unitValue = Number(raw.unitNumber);
  const unitNumber = Number.isInteger(unitValue) && unitValue > 0 ? unitValue : undefined;
  const updatedValue = Number(raw.updatedAt);

  return {
    bookCode,
    entryId,
    phase,
    ...(unitNumber === undefined ? {} : {unitNumber}),
    updatedAt: Number.isFinite(updatedValue) ? updatedValue : 0,
  };
}

export function readStudyFocus(): StudyFocus | null {
  try {
    const raw = window.localStorage.getItem(STUDY_FOCUS_STORAGE_KEY);
    return raw ? normalizeFocus(JSON.parse(raw)) : null;
  } catch {
    return null;
  }
}

export function saveStudyFocus(focus: Omit<StudyFocus, "updatedAt">): void {
  const normalized = normalizeFocus(focus);
  if (!normalized) return;
  try {
    window.localStorage.setItem(STUDY_FOCUS_STORAGE_KEY, JSON.stringify({
      ...normalized,
      updatedAt: Date.now(),
    }));
  } catch {
    // localStorage can be unavailable in privacy mode; focus remains usable
    // for the current page even when it cannot be shared across routes.
  }
}
