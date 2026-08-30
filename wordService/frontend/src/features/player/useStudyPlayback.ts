import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { AudioTarget, Entry } from "../../types";
import { materializeAudioSequence } from "./audioSequence.mjs";
import type {
  AudioSequenceConfig,
  MaterializedAudioSequenceStep,
} from "./audioSequenceTypes";
import {
  type PlaybackPhase,
  type PlaybackRunMode,
} from "./playbackSettings";
import { readStudyFocus, saveStudyFocus } from "../study/studyFocus";
import {
  playbackEndAction,
  recordCompletedPhase,
} from "./studyPlaybackState.mjs";
import { useBoundarySilence } from "./useBoundarySilence";
import { useNativeStudyPlayback } from "./useNativeStudyPlayback";
import { useStudyPlaybackSettings } from "./useStudyPlaybackSettings";

type ManualSelection = {
  entryUuid: string;
  phase: PlaybackPhase;
};

type UseStudyPlaybackOptions = {
  entries: Entry[];
  stopAfterEntry?: boolean;
  onCompleteCard?: (entry: Entry) => void;
  onConsecutiveSequenceComplete?: (entry: Entry) => void;
  /** Selects and prepares the following visible list. Returns false at the final list. */
  onFollowingList?: (entry: Entry) => boolean;
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

export function useStudyPlayback({entries, stopAfterEntry = false, onCompleteCard, onConsecutiveSequenceComplete, onFollowingList}: UseStudyPlaybackOptions) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [activeCueIndex, setActiveCueIndex] = useState(0);
  const [manualSelection, setManualSelection] = useState<ManualSelection | null>(null);
  const playbackSettings = useStudyPlaybackSettings();
  const {
    addSequenceStep,
    changePostSentenceSilence,
    changePostWordSilence,
    changePlaybackEndBehavior,
    changeSequenceStep,
    moveSequenceStep,
    playbackEndBehavior,
    playbackRunMode,
    postSentenceSilence,
    postWordSilence,
    removeSequenceStep,
    resetSettings,
    saveRunMode,
    sequence,
  } = playbackSettings;
  const [autoAdvance, setAutoAdvance] = useState(true);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playRequest, setPlayRequest] = useState(0);
  const [replayRequest, setReplayRequest] = useState(0);
  const [pauseRequest, setPauseRequest] = useState(0);
  const completedPhasesRef = useRef<{itemUuid?: string; word: boolean; sentence: boolean; cardCompleted: boolean}>({word: false, sentence: false, cardCompleted: false});
  const autoAdvanceRef = useRef(autoAdvance);
  const boundarySilence = useBoundarySilence(autoAdvanceRef);
  const {
    cancel: cancelEndTimer,
    clearTimer: clearEndTimer,
    hideState: hideSilenceState,
    isSilencePaused,
    isSilencePlaying,
    pause: pauseBoundarySilence,
    resume: resumeBoundarySilence,
    schedule: scheduleAfterSilence,
  } = boundarySilence;
  const cuesForEntry = useCallback(
    (entry: Entry | undefined) => sequenceCuesFor(sequence, entry),
    [sequence],
  );
  const activeEntry = entries[activeIndex];
  const activeCues = useMemo(
    () => cuesForEntry(activeEntry),
    [activeEntry, cuesForEntry],
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

  const requestPlayback = useCallback(() => {
    cancelEndTimer();
    autoAdvanceRef.current = true;
    setAutoAdvance(true);
    setPlayRequest((value) => value + 1);
  }, [cancelEndTimer]);

  const pauseSilence = useCallback(() => {
    pauseBoundarySilence();
    autoAdvanceRef.current = false;
    setAutoAdvance(false);
  }, [pauseBoundarySilence]);

  const resumeSilence = useCallback(() => {
    autoAdvanceRef.current = true;
    setAutoAdvance(true);
    if (!resumeBoundarySilence()) {
      requestPlayback();
    }
  }, [requestPlayback, resumeBoundarySilence]);

  const playableEntryAt = useCallback((index: number) => {
    return cuesForEntry(entries[index]);
  }, [cuesForEntry, entries]);

  const completeEntryPhase = useCallback((entry: Entry, phase: PlaybackPhase) => {
    const completion = recordCompletedPhase(
      completedPhasesRef.current,
      entry.item_uuid,
      phase,
      !!entry.sentence_audio_url,
    );
    completedPhasesRef.current = completion.progress;
    if (completion.completesCard) onCompleteCard?.(entry);
  }, [onCompleteCard]);

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

  const restartCurrentList = useCallback(() => {
    let firstIndex = 0;
    while (firstIndex < entries.length && !playableEntryAt(firstIndex).length) firstIndex += 1;
    if (firstIndex >= entries.length) {
      autoAdvanceRef.current = false;
      setAutoAdvance(false);
      return;
    }
    setActiveIndex(firstIndex);
    setActiveCueIndex(0);
    setManualSelection(null);
  }, [entries.length, playableEntryAt]);

  const advanceToFollowingList = useCallback(() => {
    if (!activeEntry || !onFollowingList?.(activeEntry)) {
      autoAdvanceRef.current = false;
      setAutoAdvance(false);
    }
  }, [activeEntry, onFollowingList]);

  const handlePlaybackEnd = useCallback(() => {
    if (activeEntry) completeEntryPhase(activeEntry, activePhase);

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
      endBehavior: playbackEndBehavior,
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
    if (action === "restart-list") {
      scheduleAfterSilence(currentPause, restartCurrentList);
      return;
    }
    if (action === "next-list") {
      scheduleAfterSilence(currentPause, advanceToFollowingList);
      return;
    }
    if (action === "complete-sequence") {
      autoAdvanceRef.current = false;
      setAutoAdvance(false);
      if (activeEntry) onConsecutiveSequenceComplete?.(activeEntry);
      return;
    }
    scheduleAfterSilence(currentPause, advanceAfterPlayback);
  }, [activeCue, activeCues.length, activeEntry, activeIndex, activePhase, advanceAfterPlayback, advanceToFollowingList, completeEntryPhase, entries.length, onConsecutiveSequenceComplete, playableEntryAt, playbackEndBehavior, playbackRunMode, postSentenceSilence, postWordSilence, restartCurrentList, safeCueIndex, scheduleAfterSilence, stopAfterEntry]);

  const handlePlayingChange = useCallback((playing: boolean) => {
    setIsPlaying(playing);
    if (playing) hideSilenceState();
  }, [hideSilenceState]);

  const activateNativeCue = useCallback((entryIndex: number, cueIndex: number) => {
    setActiveIndex(entryIndex);
    setActiveCueIndex(cueIndex);
    setManualSelection(null);
  }, []);

  const handleNativeQueueComplete = useCallback(() => {
    cancelEndTimer();
    if (playbackRunMode === "continuous" && playbackEndBehavior === "restart-list") {
      restartCurrentList();
      setPlayRequest((value) => value + 1);
      return;
    }
    if (playbackRunMode === "continuous" && playbackEndBehavior === "next-list" && activeEntry && onFollowingList?.(activeEntry)) return;
    autoAdvanceRef.current = false;
    setAutoAdvance(false);
    if (activeEntry) onConsecutiveSequenceComplete?.(activeEntry);
  }, [activeEntry, cancelEndTimer, onConsecutiveSequenceComplete, onFollowingList, playbackEndBehavior, playbackRunMode, restartCurrentList]);

  const {
    nativeQueue,
    syncQueueItem: syncNativeQueueItem,
    completeQueue: completeNativeQueue,
  } = useNativeStudyPlayback({
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
    onCompleteCue: completeEntryPhase,
    onActivateCue: activateNativeCue,
    onQueueComplete: handleNativeQueueComplete,
  });

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

  const changePlaybackRunMode = useCallback((nextMode: PlaybackRunMode) => {
    if (nextMode === playbackRunMode) return;
    cancelEndTimer();
    const continueCurrentClip = nextMode !== "single" && isPlaying;
    autoAdvanceRef.current = continueCurrentClip;
    setAutoAdvance(continueCurrentClip);
    saveRunMode(nextMode);
  }, [cancelEndTimer, isPlaying, playbackRunMode, saveRunMode]);

  const resetPlaybackSettings = useCallback(() => {
    setActiveCueIndex(0);
    setManualSelection(null);
    resetSettings();
  }, [resetSettings]);

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
    changePlaybackRunMode,
    changePostSentenceSilence,
    changePostWordSilence,
    changePlaybackEndBehavior,
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
    playbackEndBehavior,
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
    togglePlayback,
  };
}
