export function clampAudioPosition(value, duration) {
  const safeDuration = Number.isFinite(duration) ? Math.max(0, duration) : Infinity;
  const safeValue = Number.isFinite(value) ? Math.max(0, value) : 0;
  return Math.min(safeDuration, safeValue);
}

export function playbackPosition(
  anchorAudioTime,
  anchorContextTime,
  contextTime,
  boundary,
) {
  const elapsed = Math.max(0, contextTime - anchorContextTime);
  const position = anchorAudioTime + elapsed;
  return Math.min(boundary, Math.max(anchorAudioTime, position));
}

export function playableRange(start, end, duration) {
  const safeDuration = Number.isFinite(duration) ? Math.max(0, duration) : 0;
  const safeStart = clampAudioPosition(start, safeDuration);
  const safeEnd = Math.min(safeDuration, Math.max(safeStart, Number(end) || safeStart));
  return { start: safeStart, end: safeEnd };
}
