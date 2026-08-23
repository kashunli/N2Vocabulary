import { useCallback, useState } from "react";

import {
  addAudioSequenceStep,
  createDefaultAudioSequence,
  moveAudioSequenceStep,
  removeAudioSequenceStep,
  updateAudioSequenceStep,
} from "./audioSequence.mjs";
import type {
  AudioSequenceConfig,
  AudioSequenceElement,
  AudioSequenceStep,
} from "./audioSequenceTypes";
import {
  DEFAULT_PLAYBACK_RUN_MODE,
  DEFAULT_SILENCE_MS,
  readPlaybackSettings,
  savePlaybackSettings,
  type PlaybackRunMode,
} from "./playbackSettings";

/** Owns the persisted playback recipe independently of transport state. */
export function useStudyPlaybackSettings() {
  const [savedSettings] = useState(() => readPlaybackSettings());
  // Retain the legacy top-level gaps for stored-data compatibility. Recipe
  // rows now provide the authoritative pause for every playback occurrence.
  const [postWordSilence, setPostWordSilence] = useState(savedSettings.postWordSilence);
  const [postSentenceSilence, setPostSentenceSilence] = useState(savedSettings.postSentenceSilence);
  const [sequence, setSequence] = useState<AudioSequenceConfig>(savedSettings.sequence);
  const [playbackRunMode, setPlaybackRunMode] = useState<PlaybackRunMode>(savedSettings.runMode);

  const saveRunMode = useCallback((nextMode: PlaybackRunMode) => {
    setPlaybackRunMode(nextMode);
    savePlaybackSettings(postWordSilence, postSentenceSilence, nextMode, sequence);
  }, [postSentenceSilence, postWordSilence, sequence]);

  const changePostWordSilence = useCallback((value: number) => {
    setPostWordSilence(value);
    savePlaybackSettings(value, postSentenceSilence, playbackRunMode, sequence);
  }, [playbackRunMode, postSentenceSilence, sequence]);

  const changePostSentenceSilence = useCallback((value: number) => {
    setPostSentenceSilence(value);
    savePlaybackSettings(postWordSilence, value, playbackRunMode, sequence);
  }, [playbackRunMode, postWordSilence, sequence]);

  const persistSequence = useCallback((nextSequence: AudioSequenceConfig) => {
    setSequence(nextSequence);
    savePlaybackSettings(postWordSilence, postSentenceSilence, playbackRunMode, nextSequence);
  }, [playbackRunMode, postSentenceSilence, postWordSilence]);

  const changeSequenceStep = useCallback((stepId: string, patch: Partial<AudioSequenceStep>) => {
    persistSequence({
      ...sequence,
      steps: updateAudioSequenceStep(sequence.steps, stepId, patch) as AudioSequenceStep[],
    });
  }, [persistSequence, sequence]);

  const addSequenceStep = useCallback((element: AudioSequenceElement) => {
    persistSequence({
      ...sequence,
      steps: addAudioSequenceStep(
        sequence.steps,
        element,
        element === "word" ? postWordSilence : postSentenceSilence,
      ) as AudioSequenceStep[],
    });
  }, [persistSequence, postSentenceSilence, postWordSilence, sequence]);

  const removeSequenceStep = useCallback((stepId: string) => {
    persistSequence({
      ...sequence,
      steps: removeAudioSequenceStep(sequence.steps, stepId) as AudioSequenceStep[],
    });
  }, [persistSequence, sequence]);

  const moveSequenceStep = useCallback((stepId: string, direction: "up" | "down") => {
    persistSequence({
      ...sequence,
      steps: moveAudioSequenceStep(sequence.steps, stepId, direction) as AudioSequenceStep[],
    });
  }, [persistSequence, sequence]);

  const resetSettings = useCallback(() => {
    const nextSequence = createDefaultAudioSequence(
      DEFAULT_SILENCE_MS,
      DEFAULT_SILENCE_MS,
    ) as AudioSequenceConfig;
    setPostWordSilence(DEFAULT_SILENCE_MS);
    setPostSentenceSilence(DEFAULT_SILENCE_MS);
    setSequence(nextSequence);
    setPlaybackRunMode(DEFAULT_PLAYBACK_RUN_MODE);
    savePlaybackSettings(
      DEFAULT_SILENCE_MS,
      DEFAULT_SILENCE_MS,
      DEFAULT_PLAYBACK_RUN_MODE,
      nextSequence,
    );
  }, []);

  return {
    addSequenceStep,
    changePostSentenceSilence,
    changePostWordSilence,
    changeSequenceStep,
    moveSequenceStep,
    playbackRunMode,
    postSentenceSilence,
    postWordSilence,
    removeSequenceStep,
    resetSettings,
    saveRunMode,
    sequence,
  };
}
