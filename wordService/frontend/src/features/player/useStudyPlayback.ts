import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { AudioTarget, Entry } from "../../types";
import {
  addAudioSequenceStep,
  createDefaultAudioSequence,
  materializeAudioSequence,
  moveAudioSequenceStep,
  removeAudioSequenceStep,
  updateAudioSequenceStep,
} from "./audioSequence.mjs";
import type {
  AudioSequenceConfig,
  AudioSequenceElement,
  AudioSequenceStep,
  MaterializedAudioSequenceStep,
} from "./audioSequenceTypes";
import {
  DEFAULT_PLAYBACK_RUN_MODE,
  DEFAULT_SILENCE_MS,
  readPlaybackSettings,
  savePlaybackSettings,
  type PlaybackPhase,
  type PlaybackRunMode,
} from "./playbackSettings";
import { readStudyFocus, saveStudyFocus } from "../study/studyFocus";
import type { NativeAudioQueueItem } from "./nativeAudio";
import {
  nativeCueId,
  nativeCueLocation,
  playbackEndAction,
  recordCompletedPhase,
} from "./studyPlaybackState.mjs";

type PendingSilence = {
  remainingMs: number;
  startedAt: number | null;
  callback: () => void;
};

type ManualSelection = {
  entryUuid: string;
  phase: PlaybackPhase;
};

type UseStudyPlaybackOptions = {
  entries: Entry[];
  stopAfterEntry?: boolean;
  onCompleteCard?: (entry: Entry) => void;
  onConsecutiveSequenceComplete?: (entry: Entry) => void;
};

function targetFor(
  entry: Entry,
  phase: PlaybackPhase,
  sequenceOccurrenceId?: string,
): AudioTarget | null {
  const url = phase === "word" ? entry.word_audio_url : entry.sentence_audio_url;
  return url ? {entry, phase, url, sequenceOccurrenceId} : null;
}

function sequenceCuesFor(
  sequence: AudioSequenceConfig,
  entry: Entry | undefined,
): MaterializedAudioSequenceStep[] {
  if (!entry) return [];
  return materializeAudioSequence(sequence, entry) as MaterializedAudioSequenceStep[];
}

function firstCueIndexForPhase(cues: MaterializedAudioSequenceStep[], phase: PlaybackPhase) {
  return cues.findIndex((cue) => cue?.phase === phase);
}

export function useStudyPlayback({entries, stopAfterEntry = false, onCompleteCard, onConsecutiveSequenceComplete}: UseStudyPlaybackOptions) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [activeCueIndex, setActiveCueIndex] = useState(0);
  const [manualSelection, setManualSelection] = useState<ManualSelection | null>(null);
  const [savedSettings] = useState(() => readPlaybackSettings());
  // Keep the old values in the stored shape for a gentle migration. New
  // playback uses each recipe row's pauseAfterMs as its authoritative gap.
  const [postWordSilence, setPostWordSilence] = useState(savedSettings.postWordSilence);
  const [postSentenceSilence, setPostSentenceSilence] = useState(savedSettings.postSentenceSilence);
  const [sequence, setSequence] = useState<AudioSequenceConfig>(savedSettings.sequence);
  const [playbackRunMode, setPlaybackRunMode] = useState<PlaybackRunMode>(savedSettings.runMode);
  const [autoAdvance, setAutoAdvance] = useState(true);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playRequest, setPlayRequest] = useState(0);
  const [replayRequest, setReplayRequest] = useState(0);
  const [pauseRequest, setPauseRequest] = useState(0);
  const [isSilencePlaying, setIsSilencePlaying] = useState(false);
  const [isSilencePaused, setIsSilencePaused] = useState(false);
  const endTimerRef = useRef<number | null>(null);
  const endGenerationRef = useRef(0);
  const pendingSilenceRef = useRef<PendingSilence | null>(null);
  const completedPhasesRef = useRef<{itemUuid?: string; word: boolean; sentence: boolean; cardCompleted: boolean}>({word: false, sentence: false, cardCompleted: false});
  const completedNativeCueIdsRef = useRef(new Set<string>());
  const activeNativeCueIdRef = useRef<string | undefined>(undefined);
  const autoAdvanceRef = useRef(autoAdvance);
  const activeEntry = entries[activeIndex];
  const activeCues = useMemo(
    () => sequenceCuesFor(sequence, activeEntry),
    [activeEntry, sequence],
  );
  const safeCueIndex = activeCues.length ? Math.min(activeCueIndex, activeCues.length - 1) : 0;
  const sequenceCue = activeCues[safeCueIndex];
  const selectedManualPhase = manualSelection?.entryUuid && activeEntry?.item_uuid
    && manualSelection.entryUuid === activeEntry.item_uuid
    ? manualSelection.phase
    : null;
  const activePhase = selectedManualPhase || sequenceCue?.phase || "word";
  const activeCue = selectedManualPhase ? undefined : sequenceCue;
  const target = activeEntry
    ? targetFor(activeEntry, activePhase, activeCue?.occurrenceId || `manual:${activePhase}`)
    : null;

  // A complete consecutive run must be materialized before the screen locks.
  // The Android service owns this queue and its pauses, so it never depends on
  // WebView timers to move from one word/sentence to the next.
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
      const cues = sequenceCuesFor(sequence, entry);
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
  }, [activeCues, activeEntry, activeIndex, entries, postSentenceSilence, postWordSilence, safeCueIndex, selectedManualPhase, sequence, stopAfterEntry]);

  useEffect(() => {
    if (activeIndex >= entries.length) {
      setActiveIndex(0);
      setActiveCueIndex(0);
    }
  }, [activeIndex, entries.length]);

  useEffect(() => {
    if (activeCueIndex !== safeCueIndex) setActiveCueIndex(safeCueIndex);
  }, [activeCueIndex, safeCueIndex]);

  useEffect(() => {
    if (completedPhasesRef.current.itemUuid === activeEntry?.item_uuid) return;
    completedPhasesRef.current = {itemUuid: activeEntry?.item_uuid, word: false, sentence: false, cardCompleted: false};
  }, [activeEntry?.item_uuid]);

  useEffect(() => {
    if (!activeEntry) return;
    saveStudyFocus({
      bookCode: activeEntry.book_code,
      entryId: activeEntry.entry_id,
      phase: activePhase,
      unitNumber: activeEntry.unit.number,
    });
  }, [activeEntry, activePhase]);

  useEffect(() => {
    autoAdvanceRef.current = autoAdvance;
  }, [autoAdvance]);

  useEffect(() => () => {
    if (endTimerRef.current !== null) window.clearTimeout(endTimerRef.current);
  }, []);

  const resetPosition = useCallback((nextEntries: Entry[]) => {
    const savedFocus = readStudyFocus();
    const savedIndex = savedFocus && nextEntries[0]?.book_code === savedFocus.bookCode
      ? nextEntries.findIndex((entry) => entry.entry_id === savedFocus.entryId)
      : -1;
    const nextIndex = savedIndex >= 0 ? savedIndex : 0;
    const nextEntry = nextEntries[nextIndex];
    const preferredPhase = savedIndex >= 0 && savedFocus?.phase === "sentence" ? "sentence" : "word";
    const cues = sequenceCuesFor(sequence, nextEntry);
    const nextCueIndex = firstCueIndexForPhase(cues, preferredPhase);
    const hasPreferredAudio = preferredPhase === "word"
      ? !!nextEntry?.word_audio_url
      : !!nextEntry?.sentence_audio_url;
    setActiveIndex(nextIndex);
    setActiveCueIndex(nextCueIndex >= 0 ? nextCueIndex : 0);
    setManualSelection(nextCueIndex >= 0 || !hasPreferredAudio || !nextEntry
      ? null
      : {entryUuid: nextEntry.item_uuid, phase: preferredPhase});
  }, [sequence]);

  const clearEndTimer = useCallback(() => {
    endGenerationRef.current += 1;
    if (endTimerRef.current !== null) {
      window.clearTimeout(endTimerRef.current);
      endTimerRef.current = null;
    }
  }, []);

  const cancelEndTimer = useCallback(() => {
    clearEndTimer();
    pendingSilenceRef.current = null;
    setIsSilencePlaying(false);
    setIsSilencePaused(false);
  }, [clearEndTimer]);

  const startPendingSilence = useCallback(() => {
    // The AudioBuffer source has already ended, but this configured boundary
    // gap is still part of the learner's playback run. Keeping it here lets
    // Space pause/resume the gap instead of treating the ended clip as new.
    const pending = pendingSilenceRef.current;
    if (!pending) return false;

    if (pending.remainingMs <= 0) {
      pendingSilenceRef.current = null;
      setIsSilencePlaying(false);
      setIsSilencePaused(false);
      if (autoAdvanceRef.current) pending.callback();
      return true;
    }

    pending.startedAt = performance.now();
    setIsSilencePlaying(true);
    setIsSilencePaused(false);
    const generation = endGenerationRef.current;
    endTimerRef.current = window.setTimeout(() => {
      if (generation !== endGenerationRef.current) return;
      endTimerRef.current = null;
      const finished = pendingSilenceRef.current;
      pendingSilenceRef.current = null;
      setIsSilencePlaying(false);
      setIsSilencePaused(false);
      if (finished && autoAdvanceRef.current) finished.callback();
    }, pending.remainingMs);
    return true;
  }, []);

  const scheduleAfterSilence = useCallback((silenceMs: number, callback: () => void) => {
    cancelEndTimer();
    if (silenceMs <= 0) {
      callback();
      return;
    }
    pendingSilenceRef.current = {
      remainingMs: silenceMs,
      startedAt: null,
      callback,
    };
    startPendingSilence();
  }, [cancelEndTimer, startPendingSilence]);

  const requestPlayback = useCallback(() => {
    cancelEndTimer();
    autoAdvanceRef.current = true;
    setAutoAdvance(true);
    setPlayRequest((value) => value + 1);
  }, [cancelEndTimer]);

  const pauseSilence = useCallback(() => {
    const pending = pendingSilenceRef.current;
    if (!pending) {
      cancelEndTimer();
      autoAdvanceRef.current = false;
      setAutoAdvance(false);
      return;
    }

    const elapsedMs = pending.startedAt === null
      ? 0
      : Math.max(0, performance.now() - pending.startedAt);
    const remainingMs = Math.max(0, pending.remainingMs - elapsedMs);
    clearEndTimer();
    autoAdvanceRef.current = false;
    setAutoAdvance(false);
    setIsSilencePlaying(false);
    if (remainingMs > 0) {
      pendingSilenceRef.current = {...pending, remainingMs, startedAt: null};
      setIsSilencePaused(true);
    } else {
      pendingSilenceRef.current = null;
      setIsSilencePaused(false);
    }
  }, [cancelEndTimer, clearEndTimer]);

  const resumeSilence = useCallback(() => {
    if (!pendingSilenceRef.current) {
      requestPlayback();
      return;
    }
    autoAdvanceRef.current = true;
    setAutoAdvance(true);
    startPendingSilence();
  }, [requestPlayback, startPendingSilence]);

  const playableEntryAt = useCallback((index: number) => {
    const entry = entries[index];
    return entry ? sequenceCuesFor(sequence, entry) : [];
  }, [entries, sequence]);

  const selectEntry = useCallback((index: number, phase?: PlaybackPhase) => {
    if (index < 0 || index >= entries.length) return;
    const entry = entries[index];
    const cues = playableEntryAt(index);
    const preferredPhase = phase;
    const cueIndex = preferredPhase
      ? firstCueIndexForPhase(cues, preferredPhase)
      : 0;
    const directPhase = preferredPhase || cues[0]?.phase || "word";
    const hasDirectAudio = directPhase === "word" ? !!entry.word_audio_url : !!entry.sentence_audio_url;
    setActiveIndex(index);
    setActiveCueIndex(cueIndex >= 0 ? cueIndex : 0);
    setManualSelection(cueIndex >= 0 || !hasDirectAudio ? null : {entryUuid: entry.item_uuid, phase: directPhase});
    requestPlayback();
  }, [entries, playableEntryAt, requestPlayback]);

  const moveClip = useCallback((direction: -1 | 1) => {
    if (!activeEntry) return;
    const manualIndex = selectedManualPhase ? firstCueIndexForPhase(activeCues, selectedManualPhase) : -1;
    const currentCueIndex = manualIndex >= 0 ? manualIndex : safeCueIndex;
    const sameEntryCueIndex = currentCueIndex + direction;
    if (sameEntryCueIndex >= 0 && sameEntryCueIndex < activeCues.length) {
      cancelEndTimer();
      setManualSelection(null);
      setActiveCueIndex(sameEntryCueIndex);
      requestPlayback();
      return;
    }

    let nextIndex = activeIndex + direction;
    while (nextIndex >= 0 && nextIndex < entries.length && !playableEntryAt(nextIndex).length) {
      nextIndex += direction;
    }
    if (nextIndex < 0 || nextIndex >= entries.length) return;
    cancelEndTimer();
    setActiveIndex(nextIndex);
    setManualSelection(null);
    setActiveCueIndex(direction > 0 ? 0 : Math.max(0, playableEntryAt(nextIndex).length - 1));
    requestPlayback();
  }, [activeEntry, activeCues, activeIndex, cancelEndTimer, entries.length, playableEntryAt, requestPlayback, safeCueIndex, selectedManualPhase]);

  const advanceAfterPlayback = useCallback(() => {
    let nextIndex = activeIndex + 1;
    while (nextIndex < entries.length && !playableEntryAt(nextIndex).length) nextIndex += 1;
    if (!activeEntry || nextIndex >= entries.length) {
      setAutoAdvance(false);
      return;
    }
    setActiveIndex(nextIndex);
    setActiveCueIndex(0);
    setManualSelection(null);
  }, [activeEntry, activeIndex, entries.length, playableEntryAt]);

  const handlePlaybackEnd = useCallback(() => {
    if (activeEntry) {
      const completion = recordCompletedPhase(
        completedPhasesRef.current,
        activeEntry.item_uuid,
        activePhase,
        !!activeEntry.sentence_audio_url,
      );
      completedPhasesRef.current = completion.progress;
      if (completion.completesCard) onCompleteCard?.(activeEntry);
    }

    const nextCueIndex = safeCueIndex + 1;
    const currentPause = activeCue?.pauseAfterMs
      ?? (activePhase === "word" ? postWordSilence : postSentenceSilence);
    const hasNextCue = nextCueIndex < activeCues.length;
    const hasNextEntry = !stopAfterEntry && (() => {
      let nextIndex = activeIndex + 1;
      while (nextIndex < entries.length) {
        if (playableEntryAt(nextIndex).length) return true;
        nextIndex += 1;
      }
      return false;
    })();
    const action = playbackEndAction({
      autoAdvance: autoAdvanceRef.current,
      runMode: playbackRunMode,
      hasNextCue,
      hasNextEntry,
    });
    if (action === "none") return;
    if (action === "stop") {
      autoAdvanceRef.current = false;
      setAutoAdvance(false);
      return;
    }
    if (action === "next-cue") {
      scheduleAfterSilence(currentPause, () => {
        setManualSelection(null);
        setActiveCueIndex(nextCueIndex);
      });
      return;
    }
    if (action === "complete-sequence") {
      autoAdvanceRef.current = false;
      setAutoAdvance(false);
      if (activeEntry) onConsecutiveSequenceComplete?.(activeEntry);
      return;
    }
    scheduleAfterSilence(currentPause, advanceAfterPlayback);
  }, [activeCue, activeCues.length, activeEntry, activeIndex, activePhase, advanceAfterPlayback, entries.length, onCompleteCard, onConsecutiveSequenceComplete, playableEntryAt, playbackRunMode, postSentenceSilence, postWordSilence, safeCueIndex, scheduleAfterSilence, stopAfterEntry]);

  const handlePlayingChange = useCallback((playing: boolean) => {
    setIsPlaying(playing);
    if (playing) {
      setIsSilencePlaying(false);
      setIsSilencePaused(false);
    }
  }, []);

  const completeNativeCue = useCallback((id: string) => {
    if (completedNativeCueIdsRef.current.has(id)) return;
    const location = nativeCueLocation(id);
    if (!location) return;
    const entry = entries[location.entryIndex];
    const cue = entry ? playableEntryAt(location.entryIndex)[location.cueIndex] : undefined;
    if (!entry || !cue) return;
    completedNativeCueIdsRef.current.add(id);
    const completion = recordCompletedPhase(
      completedPhasesRef.current,
      entry.item_uuid,
      cue.phase,
      !!entry.sentence_audio_url,
    );
    completedPhasesRef.current = completion.progress;
    if (completion.completesCard) onCompleteCard?.(entry);
  }, [entries, onCompleteCard, playableEntryAt]);

  const syncNativeQueueItem = useCallback((id: string) => {
    const location = nativeCueLocation(id);
    if (!location || location.entryIndex < 0 || location.entryIndex >= entries.length) return;
    const cues = playableEntryAt(location.entryIndex);
    if (location.cueIndex < 0 || location.cueIndex >= cues.length) return;
    // A locked WebView may miss several service callbacks. The queue is still
    // materialized locally, so on unlock we can record every earlier cue that
    // Android has already passed before showing the current cue.
    const queuePosition = nativeQueue.findIndex((item) => item.id === id);
    if (queuePosition >= 0) {
      nativeQueue.slice(0, queuePosition).forEach((item) => completeNativeCue(item.id));
    } else if (activeNativeCueIdRef.current && activeNativeCueIdRef.current !== id) {
      completeNativeCue(activeNativeCueIdRef.current);
    }
    activeNativeCueIdRef.current = id;
    setActiveIndex(location.entryIndex);
    setActiveCueIndex(location.cueIndex);
    setManualSelection(null);
  }, [completeNativeCue, entries.length, nativeQueue, playableEntryAt]);

  const completeNativeQueue = useCallback(() => {
    if (activeNativeCueIdRef.current) completeNativeCue(activeNativeCueIdRef.current);
    activeNativeCueIdRef.current = undefined;
    cancelEndTimer();
    autoAdvanceRef.current = false;
    setAutoAdvance(false);
    setIsSilencePlaying(false);
    setIsSilencePaused(false);
    if (activeEntry) onConsecutiveSequenceComplete?.(activeEntry);
  }, [activeEntry, cancelEndTimer, completeNativeCue, onConsecutiveSequenceComplete]);

  const togglePlayback = useCallback(() => {
    if (isPlaying) {
      setPauseRequest((value) => value + 1);
    } else if (isSilencePlaying) {
      pauseSilence();
    } else if (isSilencePaused) {
      resumeSilence();
    } else {
      requestPlayback();
    }
  }, [isPlaying, isSilencePaused, isSilencePlaying, pauseSilence, requestPlayback, resumeSilence]);

  const replayFocused = useCallback(() => {
    cancelEndTimer();
    setAutoAdvance(true);
    autoAdvanceRef.current = true;
    setReplayRequest((value) => value + 1);
  }, [cancelEndTimer]);

  const persistSettings = useCallback((nextSequence: AudioSequenceConfig = sequence) => {
    savePlaybackSettings(postWordSilence, postSentenceSilence, playbackRunMode, nextSequence);
  }, [playbackRunMode, postSentenceSilence, postWordSilence, sequence]);

  const togglePlaybackRunMode = useCallback(() => {
    const nextMode: PlaybackRunMode = playbackRunMode === "single" ? "consecutive" : "single";
    cancelEndTimer();
    setPlaybackRunMode(nextMode);
    const continueCurrentClip = nextMode === "consecutive" && isPlaying;
    autoAdvanceRef.current = continueCurrentClip;
    setAutoAdvance(continueCurrentClip);
    savePlaybackSettings(postWordSilence, postSentenceSilence, nextMode, sequence);
  }, [cancelEndTimer, isPlaying, playbackRunMode, postSentenceSilence, postWordSilence, sequence]);

  const changePostWordSilence = useCallback((value: number) => {
    setPostWordSilence(value);
    savePlaybackSettings(value, postSentenceSilence, playbackRunMode, sequence);
  }, [playbackRunMode, postSentenceSilence, sequence]);

  const changePostSentenceSilence = useCallback((value: number) => {
    setPostSentenceSilence(value);
    savePlaybackSettings(postWordSilence, value, playbackRunMode, sequence);
  }, [playbackRunMode, postWordSilence, sequence]);

  const changeSequenceStep = useCallback((stepId: string, patch: Partial<AudioSequenceStep>) => {
    const nextSequence = {
      ...sequence,
      steps: updateAudioSequenceStep(sequence.steps, stepId, patch) as AudioSequenceStep[],
    };
    setSequence(nextSequence);
    persistSettings(nextSequence);
  }, [persistSettings, sequence]);

  const addSequenceStep = useCallback((element: AudioSequenceElement) => {
    const nextSequence = {
      ...sequence,
      steps: addAudioSequenceStep(sequence.steps, element, element === "word" ? postWordSilence : postSentenceSilence) as AudioSequenceStep[],
    };
    setSequence(nextSequence);
    persistSettings(nextSequence);
  }, [postSentenceSilence, postWordSilence, persistSettings, sequence]);

  const removeSequenceStep = useCallback((stepId: string) => {
    const nextSequence = {
      ...sequence,
      steps: removeAudioSequenceStep(sequence.steps, stepId) as AudioSequenceStep[],
    };
    setSequence(nextSequence);
    persistSettings(nextSequence);
  }, [persistSettings, sequence]);

  const moveSequenceStep = useCallback((stepId: string, direction: "up" | "down") => {
    const nextSequence = {
      ...sequence,
      steps: moveAudioSequenceStep(sequence.steps, stepId, direction) as AudioSequenceStep[],
    };
    setSequence(nextSequence);
    persistSettings(nextSequence);
  }, [persistSettings, sequence]);

  const resetPlaybackSettings = useCallback(() => {
    const nextSequence = createDefaultAudioSequence(DEFAULT_SILENCE_MS, DEFAULT_SILENCE_MS) as AudioSequenceConfig;
    setPostWordSilence(DEFAULT_SILENCE_MS);
    setPostSentenceSilence(DEFAULT_SILENCE_MS);
    setSequence(nextSequence);
    setPlaybackRunMode(DEFAULT_PLAYBACK_RUN_MODE);
    setActiveCueIndex(0);
    setManualSelection(null);
    savePlaybackSettings(DEFAULT_SILENCE_MS, DEFAULT_SILENCE_MS, DEFAULT_PLAYBACK_RUN_MODE, nextSequence);
  }, []);

  const selectPhase = useCallback((phase: PlaybackPhase) => {
    if (!activeEntry) return;
    const cueIndex = firstCueIndexForPhase(activeCues, phase);
    const hasAudio = phase === "word" ? !!activeEntry.word_audio_url : !!activeEntry.sentence_audio_url;
    setActiveCueIndex(cueIndex >= 0 ? cueIndex : 0);
    setManualSelection(cueIndex >= 0 || !hasAudio ? null : {entryUuid: activeEntry.item_uuid, phase});
    requestPlayback();
  }, [activeCues, activeEntry, requestPlayback]);

  const playbackActive = isPlaying || isSilencePlaying;
  const canPrevious = safeCueIndex > 0 || activeIndex > 0 || !!selectedManualPhase;
  const canNext = safeCueIndex < activeCues.length - 1 || activeIndex < entries.length - 1;

  return {
    activeEntry,
    activeIndex,
    activePhase,
    autoAdvance,
    cancelSilence: cancelEndTimer,
    canNext,
    canPrevious,
    changePostSentenceSilence,
    changePostWordSilence,
    changeSequenceStep,
    handlePlaybackEnd,
    handlePlayingChange,
    isSilencePaused,
    isSilencePlaying,
    moveClip,
    moveSequenceStep,
    nativeQueue,
    syncNativeQueueItem,
    completeNativeQueue,
    pauseRequest,
    playbackActive,
    postSentenceSilence,
    postWordSilence,
    playbackRunMode,
    playRequest,
    removeSequenceStep,
    replayFocused,
    replayRequest,
    requestPlayback,
    resetPlaybackSettings,
    resetPosition,
    selectEntry,
    selectPhase,
    sequence,
    addSequenceStep,
    target,
    togglePlaybackRunMode,
    togglePlayback,
  };
}
