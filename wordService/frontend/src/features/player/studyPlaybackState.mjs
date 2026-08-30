export function nativeCueId(entryIndex, cueIndex) {
  return `cue:${entryIndex}:${cueIndex}`;
}

export function nativeCueLocation(id) {
  const match = /^cue:(\d+):(\d+)$/.exec(id);
  if (!match) return null;
  return {entryIndex: Number(match[1]), cueIndex: Number(match[2])};
}

export function recordCompletedPhase(current, itemUuid, phase, hasSentenceAudio) {
  const progress = current?.itemUuid === itemUuid
    ? {...current}
    : {itemUuid, word: false, sentence: false, cardCompleted: false};
  progress[phase] = true;

  const completesCard = !progress.cardCompleted
    && progress.word
    && (progress.sentence || !hasSentenceAudio);
  if (completesCard) progress.cardCompleted = true;

  return {progress, completesCard};
}

export function playbackEndAction({
  autoAdvance,
  runMode,
  endBehavior,
  hasNextCue,
  hasNextEntry,
}) {
  if (!autoAdvance) return "none";
  if (runMode === "single") return "stop";
  if (hasNextCue) return "next-cue";
  if (hasNextEntry) return "next-entry";
  if (endBehavior === "restart-list") return "restart-list";
  if (endBehavior === "next-list") return "next-list";
  return "complete-sequence";
}
