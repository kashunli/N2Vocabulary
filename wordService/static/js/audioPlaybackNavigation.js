import { state } from "./state.js";

function entryHasSentence(entry) {
  return Boolean(entry?.sentence && entry.sentence.trim());
}

function entryClipsForPlayback(entry) {
  if (state.playbackMode === "words") return 1;
  if (state.playbackMode === "sentences") return entryHasSentence(entry) ? 1 : 0;
  return entryHasSentence(entry) ? 2 : 1;
}

function entryClipsForPlaybackBefore(currentIndex) {
  return state.currentEntries
    .slice(0, currentIndex)
    .reduce((total, entry) => total + entryClipsForPlayback(entry), 0);
}

function currentPlaybackClipIndex() {
  const cardIndex = Math.max(0, state.scopePlaybackPosition - 1);
  let clipIndex = entryClipsForPlaybackBefore(cardIndex);
  // In both mode the sentence is the entry's second clip; in sentences mode
  // it is the entry's only clip, so no offset.
  if (state.scopePlaybackPhase === "sentence" && state.playbackMode === "both") clipIndex += 1;
  return clipIndex;
}

function clipTargetForOffset(offset) {
  const currentClip = currentPlaybackClipIndex();
  const clips = state.currentEntries.reduce(
    (total, entry) => total + entryClipsForPlayback(entry),
    0,
  );
  const targetClip = currentClip + Math.sign(offset);
  if (targetClip < 0 || targetClip >= clips) return null;

  let clipIndex = targetClip;
  for (let entryIndex = 0; entryIndex < state.currentEntries.length; entryIndex += 1) {
    const entry = state.currentEntries[entryIndex];
    if (state.playbackMode === "words") {
      if (clipIndex === 0) return {entryIndex, phase: "word"};
      clipIndex -= 1;
      continue;
    }
    if (state.playbackMode === "sentences") {
      if (!entryHasSentence(entry)) continue;
      if (clipIndex === 0) return {entryIndex, phase: "sentence"};
      clipIndex -= 1;
      continue;
    }
    if (clipIndex === 0) return {entryIndex, phase: "word"};
    clipIndex -= 1;
    if (entryHasSentence(entry)) {
      if (clipIndex === 0) return {entryIndex, phase: "sentence"};
      clipIndex -= 1;
    }
  }
  return null;
}
export { clipTargetForOffset };
