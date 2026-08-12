/**
 * Decide what should happen after the focused clip finishes. The transport
 * mode is deliberately separate from the content mode: content mode chooses
 * word/sentence clips, while transport mode decides whether the run stops or
 * continues through the visible list.
 */
export function nextPlaybackStep({
  playbackMode,
  playbackRunMode,
  phase,
  hasSentence,
  hasNextEntry,
}) {
  if (playbackRunMode === "single") return "stop";
  if (playbackMode === "both" && phase === "word" && hasSentence) return "sentence";
  return hasNextEntry ? "next-word" : "stop";
}
