export function clampIndex(index, length) {
  if (length <= 0) return 0;
  return Math.min(length - 1, Math.max(0, index));
}

export function nextLineAction(index, length) {
  return length > 0 && index >= length - 1 ? "next-passage" : "next-line";
}

export function lineIndexForTime(segments, time) {
  if (!segments.length) return 0;
  const exact = segments.findIndex(
    (segment) => time >= segment.start_ms / 1000 && time < segment.end_ms / 1000,
  );
  if (exact >= 0) return exact;
  if (time < segments[0].start_ms / 1000) return 0;
  // Keep the last spoken line active during the intentional gap before the
  // next line instead of jumping to the final line of the passage.
  let latestStarted = 0;
  for (let index = 1; index < segments.length; index += 1) {
    if (time < segments[index].start_ms / 1000) break;
    latestStarted = index;
  }
  return latestStarted;
}

export function toggleMarked(previous, segmentId) {
  const next = new Set(previous);
  if (next.has(segmentId)) next.delete(segmentId);
  else next.add(segmentId);
  return next;
}

export function sentencePlaybackWindow(
  segments,
  index,
  audioDurationMs,
) {
  const segment = segments?.[index];
  if (!segment) return { start: 0, end: 0 };
  const duration = Number.isFinite(audioDurationMs) ? Math.max(0, audioDurationMs / 1000) : Infinity;

  // Stored endpoints are the playback authority. Referring to a neighbor here
  // would erase the intentional gaps and overlaps created by manual editing.
  return {
    start: Math.max(0, segment.start_ms / 1000),
    end: Math.min(duration, segment.end_ms / 1000),
  };
}

export function playerActionForKey(event) {
  if (event.ctrlKey || event.metaKey || event.altKey) return null;
  if (event.code === "Space") return "toggle-play";

  switch (event.key.toLowerCase()) {
    case "q":
      return "previous-pause";
    case "e":
      return "next-pause";
    case "r":
      return "replay";
    case "b":
      return "toggle-blur";
    case "f":
      return "toggle-mark";
    case "n":
    case "d":
    case "arrowright":
      return "next-line";
    case "a":
    case "arrowleft":
      return "previous-line";
    default:
      return null;
  }
}

export function adjacentNavigationPoint(points, currentTime, direction, tolerance = 0.04) {
  if (!Array.isArray(points) || !Number.isFinite(currentTime)) return null;
  const safeTolerance = Number.isFinite(tolerance) ? Math.max(0, tolerance) : 0;

  if (direction === "next") {
    return points.find((point) => point > currentTime + safeTolerance) ?? null;
  }
  if (direction === "previous") {
    for (let index = points.length - 1; index >= 0; index -= 1) {
      if (points[index] < currentTime - safeTolerance) return points[index];
    }
  }
  return null;
}

export function endpointEditWindow(previous, current, following, endpoint, audioDurationMs) {
  if (!current) return null;
  if (endpoint === "start") {
    return {
      startMs: Math.max(0, Number(previous?.start_ms) || 0),
      endMs: current.end_ms,
    };
  }
  return {
    startMs: current.start_ms,
    endMs: Math.min(
      Number.isFinite(audioDurationMs) ? audioDurationMs : current.end_ms,
      Number(following?.end_ms) || audioDurationMs || current.end_ms,
    ),
  };
}

export function clampLineEndpointMs(
  value,
  segment,
  endpoint,
  windowStartMs,
  windowEndMs,
  minimumLineMs = 100,
) {
  const minimum = endpoint === "start"
    ? Math.max(0, Number(windowStartMs))
    : Number(segment?.start_ms) + minimumLineMs;
  const maximum = endpoint === "start"
    ? Number(segment?.end_ms) - minimumLineMs
    : Number(windowEndMs);
  if (!Number.isFinite(minimum) || !Number.isFinite(maximum) || maximum < minimum) return 0;
  const rounded = Math.round(Number(value) / 10) * 10;
  return Math.min(maximum, Math.max(minimum, Number.isFinite(rounded) ? rounded : minimum));
}

export function formatMilliseconds(value) {
  const safe = Number.isFinite(value) ? Math.max(0, Math.round(value)) : 0;
  const minutes = Math.floor(safe / 60000);
  const seconds = Math.floor((safe % 60000) / 1000);
  const milliseconds = safe % 1000;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}.${String(milliseconds).padStart(3, "0")}`;
}

export function formatTime(value) {
  const safe = Number.isFinite(value) ? Math.max(0, value) : 0;
  const minutes = Math.floor(safe / 60);
  const seconds = Math.floor(safe % 60);
  return [minutes, seconds].map((part) => String(part).padStart(2, "0")).join(":");
}

export function formatSecondsMilliseconds(value) {
  const safeMilliseconds = Number.isFinite(value)
    ? Math.max(0, Math.round(value * 1000))
    : 0;
  const seconds = Math.floor(safeMilliseconds / 1000);
  const hundredths = Math.floor((safeMilliseconds % 1000) / 10);
  return `${String(seconds).padStart(2, "0")}:${String(hundredths).padStart(2, "0")}`;
}

