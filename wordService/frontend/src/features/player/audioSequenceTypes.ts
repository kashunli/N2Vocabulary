import type { PlaybackPhase } from "./playbackSettings";

export type AudioSequenceElement = PlaybackPhase;

export interface AudioSequenceStep {
  id: string;
  element: AudioSequenceElement;
  repeatCount: number;
  pauseAfterMs: number;
}

export interface AudioSequenceConfig {
  version: number;
  steps: AudioSequenceStep[];
}

export interface MaterializedAudioSequenceStep extends AudioSequenceStep {
  phase: PlaybackPhase;
  sequenceIndex: number;
  repeatIndex: number;
  occurrenceId: string;
}

