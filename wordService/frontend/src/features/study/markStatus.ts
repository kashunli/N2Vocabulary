export type MarkStatus = "unmarked" | "known" | "flagged";

export function normalizeMarkStatus(value: unknown): MarkStatus {
  if (value === "flagged") return "flagged";
  if (value === "known") return "known";
  return "unmarked";
}

export function statusFromLegacyMark(known: unknown, flagged: unknown): MarkStatus {
  // Flagged deliberately wins when old data contains both booleans.
  if (flagged === true) return "flagged";
  if (known === true) return "known";
  return "unmarked";
}

export function markStatusOf(mark?: {
  status?: unknown;
  known?: unknown;
  flagged?: unknown;
}): MarkStatus {
  if (!mark) return "unmarked";
  if (mark.flagged === true) return "flagged";
  if (mark.status === "flagged") return "flagged";
  if (mark.status === "known" || mark.known === true) return "known";
  return normalizeMarkStatus(mark.status);
}

export function toggleMarkStatus(
  current: MarkStatus,
  requested: Exclude<MarkStatus, "unmarked">,
): MarkStatus {
  return current === requested ? "unmarked" : requested;
}
