import { useEffect, useState } from "react";

import { MAX_AUDIO_SEQUENCE_STEPS, MAX_SEQUENCE_PAUSE_MS } from "./audioSequence.mjs";
import type {
  AudioSequenceConfig,
  AudioSequenceElement,
  AudioSequenceStep,
} from "./audioSequenceTypes";
import {
  nextPlaybackRunMode,
  playbackRunModeDescription,
  playbackRunModeLabel,
  type PlaybackRunMode,
} from "./playbackSettings";

interface PlaybackSettingsModalProps {
  playbackRunMode: PlaybackRunMode;
  sequence: AudioSequenceConfig;
  onChangeSequenceStep: (stepId: string, patch: Partial<AudioSequenceStep>) => void;
  onAddSequenceStep: (element: AudioSequenceElement) => void;
  onMoveSequenceStep: (stepId: string, direction: "up" | "down") => void;
  onRemoveSequenceStep: (stepId: string) => void;
  onTogglePlaybackRunMode: () => void;
  onClose: () => void;
  onReset: () => void;
}

function pauseSeconds(value: number) {
  return (value / 1000).toFixed(1);
}

interface PauseAfterControlProps {
  stepIndex: number;
  value: number;
  onChange: (value: number) => void;
}

function PauseAfterControl({stepIndex, value, onChange}: PauseAfterControlProps) {
  const [draft, setDraft] = useState(pauseSeconds(value));

  useEffect(() => {
    setDraft(pauseSeconds(value));
  }, [value]);

  const commitDraft = () => {
    const seconds = Number(draft);
    if (!Number.isFinite(seconds)) {
      setDraft(pauseSeconds(value));
      return;
    }
    const boundedSeconds = Math.min(MAX_SEQUENCE_PAUSE_MS / 1000, Math.max(0, seconds));
    const milliseconds = Math.round(boundedSeconds * 10) * 100;
    onChange(milliseconds);
    setDraft(pauseSeconds(milliseconds));
  };

  return (
    <span className="react-sequence-slider-row">
      <input
        type="range"
        min="0"
        max={MAX_SEQUENCE_PAUSE_MS / 1000}
        step="0.1"
        value={value / 1000}
        aria-label={`Pause after step ${stepIndex}`}
        onChange={(event) => onChange(Math.round(Number(event.target.value) * 1000))}
      />
      <span className="react-sequence-pause-value">
        <input
          className="react-sequence-pause-input"
          type="number"
          min="0"
          max={MAX_SEQUENCE_PAUSE_MS / 1000}
          step="0.1"
          inputMode="decimal"
          value={draft}
          aria-label={`Pause after step ${stepIndex} in seconds`}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={commitDraft}
          onKeyDown={(event) => {
            if (event.key === "Enter") event.currentTarget.blur();
            if (event.key === "Escape") {
              setDraft(pauseSeconds(value));
              event.currentTarget.blur();
            }
          }}
        />
        <span aria-hidden="true">s</span>
      </span>
    </span>
  );
}

export function PlaybackSettingsModal({
  playbackRunMode,
  sequence,
  onChangeSequenceStep,
  onAddSequenceStep,
  onMoveSequenceStep,
  onRemoveSequenceStep,
  onTogglePlaybackRunMode,
  onClose,
  onReset,
}: PlaybackSettingsModalProps) {
  return (
    <div className="react-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="react-settings-modal react-sequence-modal" role="dialog" aria-modal="true" aria-labelledby="react-settings-title">
        <div className="react-settings-head">
          <div>
            <span className="eyebrow">PLAYBACK RECIPE</span>
            <h2 id="react-settings-title">Listening sequence</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close playback settings">×</button>
        </div>
        <div className="react-settings-body">
          <div className="react-sequence-intro">
            <p>Each row is one playback occurrence. Add the same audio more than once when you want it repeated later.</p>
            <span>{sequence.steps.length}/{MAX_AUDIO_SEQUENCE_STEPS} steps</span>
          </div>

          <div className="react-sequence-list" role="list" aria-label="Listening sequence steps">
            {sequence.steps.map((step, index) => (
              <div className="react-sequence-row" role="listitem" key={step.id}>
                <span className="react-sequence-number" aria-hidden="true">{index + 1}</span>
                <div className="react-sequence-main">
                  <label htmlFor={`react-sequence-element-${step.id}`}>Audio element</label>
                  <select
                    id={`react-sequence-element-${step.id}`}
                    value={step.element}
                    onChange={(event) => onChangeSequenceStep(step.id, {element: event.target.value as AudioSequenceElement})}
                  >
                    <option value="word">Word</option>
                    <option value="sentence">Sentence</option>
                  </select>
                  <small>Unavailable audio is skipped automatically.</small>
                </div>
                <div className="react-sequence-controls">
                  <div className="react-sequence-order" aria-label={`Move step ${index + 1}`}>
                    <button type="button" onClick={() => onMoveSequenceStep(step.id, "up")} disabled={index === 0} aria-label={`Move step ${index + 1} up`}>↑</button>
                    <button type="button" onClick={() => onMoveSequenceStep(step.id, "down")} disabled={index === sequence.steps.length - 1} aria-label={`Move step ${index + 1} down`}>↓</button>
                  </div>
                  <div className="react-sequence-stepper">
                    <span>Repeat</span>
                    <span className="react-sequence-stepper-control">
                      <button type="button" onClick={() => onChangeSequenceStep(step.id, {repeatCount: Math.max(0, step.repeatCount - 1)})} disabled={step.repeatCount <= 0} aria-label={`Decrease repeat for step ${index + 1}`}>−</button>
                      <output aria-label={`Repeat count for step ${index + 1}`}>{step.repeatCount}</output>
                      <button type="button" onClick={() => onChangeSequenceStep(step.id, {repeatCount: Math.min(9, step.repeatCount + 1)})} disabled={step.repeatCount >= 9} aria-label={`Increase repeat for step ${index + 1}`}>+</button>
                    </span>
                  </div>
                  <div className="react-sequence-field">
                    <span>Pause after</span>
                    <PauseAfterControl
                      stepIndex={index + 1}
                      value={step.pauseAfterMs}
                      onChange={(pauseAfterMs) => onChangeSequenceStep(step.id, {pauseAfterMs})}
                    />
                  </div>
                  <button type="button" className="react-sequence-remove" onClick={() => onRemoveSequenceStep(step.id)} disabled={sequence.steps.length <= 1} aria-label={`Remove step ${index + 1}`}>Remove</button>
                </div>
              </div>
            ))}
          </div>

          <div className="react-sequence-add">
            <span>Add step</span>
            <button type="button" onClick={() => onAddSequenceStep("word")} disabled={sequence.steps.length >= MAX_AUDIO_SEQUENCE_STEPS}>+ Word</button>
            <button type="button" onClick={() => onAddSequenceStep("sentence")} disabled={sequence.steps.length >= MAX_AUDIO_SEQUENCE_STEPS}>+ Sentence</button>
          </div>

          <div className="react-setting-copy">
            <span>List playback</span>
            <p>{playbackRunModeDescription(playbackRunMode)}</p>
          </div>
          <button type="button" className="react-sequence-run-mode" onClick={onTogglePlaybackRunMode} aria-pressed={playbackRunMode !== "single"}>
            {playbackRunModeLabel(playbackRunMode)} → {playbackRunModeLabel(nextPlaybackRunMode(playbackRunMode))}
          </button>

          <button type="button" className="react-settings-reset" onClick={onReset}>Reset sequence</button>
        </div>
      </section>
    </div>
  );
}
