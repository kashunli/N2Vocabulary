import type { Entry, UnitSummary } from "../../types";

export function unitLabel(unit?: UnitSummary | Entry["unit"]) {
  if (!unit) return "All sections";
  return `U${String(unit.number).padStart(2, "0")} ${unit.title || unit.header}`;
}
