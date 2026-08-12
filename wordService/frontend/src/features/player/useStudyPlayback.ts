import { useCallback, useEffect, useRef, useState } from "react";

import type { AudioTarget, Entry } from "../../types";
import {
  DEFAULT_PLAYBACK_RUN_MODE,
  DEFAULT_SILENCE_MS,
  readPlaybackSettings,
  savePlaybackSettings,
  type PlaybackMode,
  type PlaybackPhase,
  type PlaybackRunMode,
} from "./playbackSettings";
import { nextPlaybackStep } from "./playbackSequence.mjs";
import { readStudyFocus, saveStudyFocus } from "../study/studyFocus";

type PendingSilence = {
  remainingMs: number;
  startedAt: number | null;
  callback: () => void;
};

type UseStudyPlaybackOptions = {
  entries: Entry[];
  showStarred: boolean;
};

function targetFor(entry: Entry, phase: PlaybackPhase): AudioTarget | null {
  const url = phase === "word" ? entry.word_audio_url : entry.sentence_audio_url;
  return url ? {entry, phase, url} : null;
}

export function useStudyPlayback({entries, showStarred}: UseStudyPlaybackOptions) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [activePhase, setActivePhase] = useState<PlaybackPhase>("word");
  const [savedSettings] = useState(() => readPlaybackSettings());
  const [postWordSilence, setPostWordSilence] = useState(savedSettings.postWordSilence);
  const [postSentenceSilence, setPostSentenceSilence] = useState(savedSettings.postSentenceSilence);
  const [playbackMode, setPlaybackMode] = useState<PlaybackMode>(savedSettings.mode);
  const [playbackRunMode, setPlaybackRunMode] = useState<PlaybackRunMode>(savedSettings.runMode);
  const [autoAdvance, setAutoAdvance] = useState(true);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playRequest, setPlayRequest] = useState(0);
  const [replayRequest, setReplayRequest] = useState(0);
  const [pauseRequest, setPauseRequest] = useState(0);
  const [stopRequest, setStopRequest] = useState(0);
  const [isSilencePlaying, setIsSilencePlaying] = useState(false);
  const [isSilencePaused, setIsSilencePaused] = useState(false);
  const endTimerRef = useRef<number | null>(null);
  const endGenerationRef = useRef(0);
  const pendingSilenceRef = useRef<PendingSilence | null>(null);
  const autoAdvanceRef = useRef(autoAdvance);
  const activeEntry = entries[activeIndex];
  const target = activeEntry ? targetFor(activeEntry, activePhase) : null;

  useEffect(() => {
    if (!activeEntry || showStarred) return;
    saveStudyFocus({
      bookCode: activeEntry.book_code,
      entryId: activeEntry.entry_id,
      phase: activePhase,
      unitNumber: activeEntry.unit.number,
    });
  }, [activeEntry, activePhase, showStarred]);

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
    const nextPhase = savedIndex >= 0 && savedFocus?.phase === "sentence" && nextEntry?.sentence_audio_url
      ? "sentence"
      : playbackMode === "sentences" && nextEntry?.sentence_audio_url
        ? "sentence"
        : "word";
    setActiveIndex(nextIndex);
    setActivePhase(nextPhase);
  }, [playbackMode]);

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

  const selectEntry = useCallback((index: number, phase?: PlaybackPhase) => {
    if (index < 0 || index >= entries.length) return;
    cancelEndTimer();
    const nextPhase = phase || (playbackMode === "sentences" && entries[index].sentence_audio_url ? "sentence" : "word");
    setActiveIndex(index);
    setActivePhase(nextPhase);
    requestPlayback();
  }, [cancelEndTimer, entries, playbackMode, requestPlayback]);

  const moveClip = useCallback((direction: -1 | 1) => {
    if (!activeEntry || showStarred) return;
    let nextIndex = activeIndex;
    let nextPhase: PlaybackPhase = activePhase;
    if (playbackMode === "words") {
      nextIndex += direction;
      nextPhase = "word";
    } else if (playbackMode === "sentences") {
      nextIndex += direction;
      nextPhase = "sentence";
    } else if (direction > 0) {
      if (activePhase === "word" && activeEntry.sentence_audio_url) {
        nextPhase = "sentence";
      } else {
        nextIndex += 1;
        nextPhase = "word";
      }
    } else if (activePhase === "sentence") {
      nextPhase = "word";
    } else if (activeIndex > 0) {
      nextIndex -= 1;
      nextPhase = entries[nextIndex]?.sentence_audio_url ? "sentence" : "word";
    }
    if (nextIndex < 0 || nextIndex >= entries.length || (nextIndex === activeIndex && nextPhase === activePhase)) return;
    cancelEndTimer();
    setActiveIndex(nextIndex);
    setActivePhase(nextPhase);
    requestPlayback();
  }, [activeEntry, activeIndex, activePhase, cancelEndTimer, entries, playbackMode, requestPlayback, showStarred]);

  const advanceAfterPlayback = useCallback(() => {
    if (!activeEntry || activeIndex >= entries.length - 1) {
      setAutoAdvance(false);
      return;
    }
    setActiveIndex(activeIndex + 1);
    setActivePhase(playbackMode === "sentences" ? "sentence" : "word");
  }, [activeEntry, activeIndex, entries.length, playbackMode]);

  const handlePlaybackEnd = useCallback(() => {
    if (!autoAdvanceRef.current) return;
    const nextStep = nextPlaybackStep({
      playbackMode,
      playbackRunMode,
      phase: activePhase,
      hasSentence: !!activeEntry?.sentence_audio_url,
      hasNextEntry: activeIndex < entries.length - 1,
    });
    if (nextStep === "stop") {
      autoAdvanceRef.current = false;
      setAutoAdvance(false);
      return;
    }
    if (nextStep === "sentence") {
      scheduleAfterSilence(postWordSilence, () => setActivePhase("sentence"));
      return;
    }
    scheduleAfterSilence(activePhase === "word" ? postWordSilence : postSentenceSilence, advanceAfterPlayback);
  }, [activeEntry, activeIndex, activePhase, advanceAfterPlayback, entries.length, playbackMode, playbackRunMode, postSentenceSilence, postWordSilence, scheduleAfterSilence]);

  const handlePlayingChange = useCallback((playing: boolean) => {
    setIsPlaying(playing);
    if (playing) {
      setIsSilencePlaying(false);
      setIsSilencePaused(false);
    }
  }, []);

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
    setReplayRequest((value) => value + 1);
  }, [cancelEndTimer]);

  const stopPlayback = useCallback(() => {
    cancelEndTimer();
    autoAdvanceRef.current = false;
    setAutoAdvance(false);
    setStopRequest((value) => value + 1);
  }, [cancelEndTimer]);

  const changePlaybackMode = useCallback((mode: PlaybackMode) => {
    cancelEndTimer();
    setPlaybackMode(mode);
    setActivePhase(mode === "sentences" && activeEntry?.sentence_audio_url ? "sentence" : "word");
    savePlaybackSettings(postWordSilence, postSentenceSilence, mode, playbackRunMode);
  }, [activeEntry, cancelEndTimer, playbackRunMode, postSentenceSilence, postWordSilence]);

  const togglePlaybackRunMode = useCallback(() => {
    const nextMode: PlaybackRunMode = playbackRunMode === "single" ? "consecutive" : "single";
    cancelEndTimer();
    setPlaybackRunMode(nextMode);
    const continueCurrentClip = nextMode === "consecutive" && isPlaying;
    autoAdvanceRef.current = continueCurrentClip;
    setAutoAdvance(continueCurrentClip);
    savePlaybackSettings(postWordSilence, postSentenceSilence, playbackMode, nextMode);
  }, [cancelEndTimer, isPlaying, playbackMode, playbackRunMode, postSentenceSilence, postWordSilence]);

  const changePostWordSilence = useCallback((value: number) => {
    setPostWordSilence(value);
    savePlaybackSettings(value, postSentenceSilence, playbackMode, playbackRunMode);
  }, [playbackMode, playbackRunMode, postSentenceSilence]);

  const changePostSentenceSilence = useCallback((value: number) => {
    setPostSentenceSilence(value);
    savePlaybackSettings(postWordSilence, value, playbackMode, playbackRunMode);
  }, [playbackMode, playbackRunMode, postWordSilence]);

  const resetPlaybackSettings = useCallback(() => {
    setPostWordSilence(DEFAULT_SILENCE_MS);
    setPostSentenceSilence(DEFAULT_SILENCE_MS);
    setPlaybackMode("both");
    setPlaybackRunMode(DEFAULT_PLAYBACK_RUN_MODE);
    savePlaybackSettings(DEFAULT_SILENCE_MS, DEFAULT_SILENCE_MS, "both", DEFAULT_PLAYBACK_RUN_MODE);
  }, []);

  const selectPhase = useCallback((phase: PlaybackPhase) => {
    setActivePhase(phase);
    requestPlayback();
  }, [requestPlayback]);

  const playbackActive = isPlaying || isSilencePlaying;
  const canPrevious = !showStarred && (activeIndex > 0 || (playbackMode === "both" && activePhase === "sentence"));
  const canNext = !showStarred && (activeIndex < entries.length - 1 || (playbackMode === "both" && activePhase === "word" && !!activeEntry?.sentence_audio_url));

  return {
    activeEntry,
    activeIndex,
    activePhase,
    autoAdvance,
    canNext,
    canPrevious,
    changePlaybackMode,
    changePostSentenceSilence,
    changePostWordSilence,
    handlePlaybackEnd,
    handlePlayingChange,
    isSilencePaused,
    isSilencePlaying,
    moveClip,
    pauseRequest,
    playbackActive,
    playbackMode,
    postSentenceSilence,
    postWordSilence,
    playbackRunMode,
    playRequest,
    replayFocused,
    replayRequest,
    requestPlayback,
    resetPlaybackSettings,
    resetPosition,
    selectEntry,
    selectPhase,
    stopPlayback,
    stopRequest,
    target,
    togglePlaybackRunMode,
    togglePlayback,
  };
}
