import { useCallback, useMemo, useRef } from "react";

import type { Entry } from "../../types";
import type { MaterializedAudioSequenceStep } from "./audioSequenceTypes";
import type { NativeAudioQueueItem } from "./nativeAudio";
import type { PlaybackPhase } from "./playbackSettings";
import { nativeCueId, nativeCueLocation } from "./studyPlaybackState.mjs";

type UseNativeStudyPlaybackOptions = {
  entries: Entry[];
  activeEntry: Entry | undefined;
  activeIndex: number;
  activeCues: MaterializedAudioSequenceStep[];
  safeCueIndex: number;
  selectedManualPhase: PlaybackPhase | null;
  stopAfterEntry: boolean;
  postWordSilence: number;
  postSentenceSilence: number;
  cuesForEntry: (entry: Entry | undefined) => MaterializedAudioSequenceStep[];
  onCompleteCue: (entry: Entry, phase: PlaybackPhase) => void;
  onActivateCue: (entryIndex: number, cueIndex: number) => void;
  onQueueComplete: () => void;
};

function firstCueIndexForPhase(
  cues: MaterializedAudioSequenceStep[],
  phase: PlaybackPhase,
) {
  return cues.findIndex((cue) => cue.phase === phase);
}

/** Bridges the deterministic study sequence to the Android audio service. */
export function useNativeStudyPlayback({
  entries,
  activeEntry,
  activeIndex,
  activeCues,
  safeCueIndex,
  selectedManualPhase,
  stopAfterEntry,
  postWordSilence,
  postSentenceSilence,
  cuesForEntry,
  onCompleteCue,
  onActivateCue,
  onQueueComplete,
}: UseNativeStudyPlaybackOptions) {
  const completedCueIdsRef = useRef(new Set<string>());
  const activeCueIdRef = useRef<string | undefined>(undefined);

  // The entire queue must exist before the screen locks because Android—not
  // WebView timers—owns advancement and configured pauses in the background.
  const nativeQueue = useMemo((): NativeAudioQueueItem[] => {
    if (!activeEntry) return [];
    const selectedCueIndex = selectedManualPhase
      ? firstCueIndexForPhase(activeCues, selectedManualPhase)
      : safeCueIndex;
    const firstCueIndex = selectedCueIndex >= 0 ? selectedCueIndex : safeCueIndex;
    const result: NativeAudioQueueItem[] = [];

    for (let entryIndex = activeIndex; entryIndex < entries.length; entryIndex += 1) {
      if (entryIndex > activeIndex && stopAfterEntry) break;
      const entry = entries[entryIndex];
      const cues = cuesForEntry(entry);
      const startCueIndex = entryIndex === activeIndex ? firstCueIndex : 0;
      for (let cueIndex = startCueIndex; cueIndex < cues.length; cueIndex += 1) {
        const cue = cues[cueIndex];
        const url = cue.phase === "word" ? entry.word_audio_url : entry.sentence_audio_url;
        if (!url) continue;
        result.push({
          id: nativeCueId(entryIndex, cueIndex),
          title: `${entry.kanji} · ${cue.phase === "word" ? "Word" : "Sentence"}`,
          url,
          pauseAfterMs: cue.pauseAfterMs
            ?? (cue.phase === "word" ? postWordSilence : postSentenceSilence),
        });
      }
      if (stopAfterEntry) break;
    }
    return result;
  }, [activeCues, activeEntry, activeIndex, cuesForEntry, entries, postSentenceSilence, postWordSilence, safeCueIndex, selectedManualPhase, stopAfterEntry]);

  const completeCue = useCallback((id: string) => {
    if (completedCueIdsRef.current.has(id)) return;
    const location = nativeCueLocation(id);
    if (!location) return;
    const entry = entries[location.entryIndex];
    const cue = entry ? cuesForEntry(entry)[location.cueIndex] : undefined;
    if (!entry || !cue) return;
    completedCueIdsRef.current.add(id);
    onCompleteCue(entry, cue.phase);
  }, [cuesForEntry, entries, onCompleteCue]);

  const syncQueueItem = useCallback((id: string) => {
    const location = nativeCueLocation(id);
    if (!location || location.entryIndex < 0 || location.entryIndex >= entries.length) return;
    const cues = cuesForEntry(entries[location.entryIndex]);
    if (location.cueIndex < 0 || location.cueIndex >= cues.length) return;

    // The WebView can miss service callbacks while locked. Complete every
    // earlier materialized cue before reflecting Android's current position.
    const queuePosition = nativeQueue.findIndex((item) => item.id === id);
    if (queuePosition >= 0) {
      nativeQueue.slice(0, queuePosition).forEach((item) => completeCue(item.id));
    } else if (activeCueIdRef.current && activeCueIdRef.current !== id) {
      completeCue(activeCueIdRef.current);
    }
    activeCueIdRef.current = id;
    onActivateCue(location.entryIndex, location.cueIndex);
  }, [completeCue, cuesForEntry, entries, nativeQueue, onActivateCue]);

  const completeQueue = useCallback(() => {
    if (activeCueIdRef.current) completeCue(activeCueIdRef.current);
    activeCueIdRef.current = undefined;
    onQueueComplete();
  }, [completeCue, onQueueComplete]);

  return {nativeQueue, syncQueueItem, completeQueue};
}
