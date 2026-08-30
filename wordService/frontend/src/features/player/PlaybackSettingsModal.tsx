import { useEffect, useState } from "react";

import { useI18n, type AppLanguage } from "../../i18n";
import { AccountControls, type AccountState } from "../study/AccountControls";
import { MAX_AUDIO_SEQUENCE_STEPS, MAX_SEQUENCE_PAUSE_MS } from "./audioSequence.mjs";
import type {
  AudioSequenceConfig,
  AudioSequenceElement,
  AudioSequenceStep,
} from "./audioSequenceTypes";
import {
  PLAYBACK_END_BEHAVIOR_ORDER,
  PLAYBACK_RUN_MODE_ORDER,
  type PlaybackEndBehavior,
  type PlaybackRunMode,
} from "./playbackSettings";

interface PlaybackSettingsModalProps {
  accountState: AccountState;
  playbackRunMode: PlaybackRunMode;
  playbackEndBehavior: PlaybackEndBehavior;
  sequence: AudioSequenceConfig;
  onChangeSequenceStep: (stepId: string, patch: Partial<AudioSequenceStep>) => void;
  onAddSequenceStep: (element: AudioSequenceElement) => void;
  onMoveSequenceStep: (stepId: string, direction: "up" | "down") => void;
  onRemoveSequenceStep: (stepId: string) => void;
  onChangePlaybackRunMode: (mode: PlaybackRunMode) => void;
  onChangePlaybackEndBehavior: (behavior: PlaybackEndBehavior) => void;
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
  const {copy} = useI18n();
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
        aria-label={copy.settings.pauseAfterStep(stepIndex)}
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
          aria-label={copy.settings.pauseAfterStepSeconds(stepIndex)}
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
  accountState,
  playbackRunMode,
  playbackEndBehavior,
  sequence,
  onChangeSequenceStep,
  onAddSequenceStep,
  onMoveSequenceStep,
  onRemoveSequenceStep,
  onChangePlaybackRunMode,
  onChangePlaybackEndBehavior,
  onClose,
  onReset,
}: PlaybackSettingsModalProps) {
  const {copy, language, setLanguage} = useI18n();
  return (
    <div className="react-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="react-settings-modal react-sequence-modal" role="dialog" aria-modal="true" aria-labelledby="react-settings-title">
        <div className="react-settings-head">
          <div>
            <span className="eyebrow">{copy.settings.eyebrow}</span>
            <h2 id="react-settings-title">{copy.settings.title}</h2>
          </div>
          <button type="button" onClick={onClose} aria-label={copy.settings.close}>×</button>
        </div>
        <div className="react-settings-body">
          <label className="react-language-picker react-settings-language">
            <span>{copy.languageLabel}</span>
            <select value={language} onChange={(event) => setLanguage(event.target.value as AppLanguage)} aria-label={copy.languageLabel}>
              <option value="en">{copy.english}</option>
              <option value="zh">{copy.chinese}</option>
            </select>
          </label>
          <div className="react-sequence-intro">
            <p>{copy.settings.introduction}</p>
            <span>{copy.settings.steps(sequence.steps.length, MAX_AUDIO_SEQUENCE_STEPS)}</span>
          </div>

          <div className="react-sequence-list" role="list" aria-label={copy.settings.sequenceSteps}>
            {sequence.steps.map((step, index) => (
              <div className="react-sequence-row" role="listitem" key={step.id}>
                <span className="react-sequence-number" aria-hidden="true">{index + 1}</span>
                <div className="react-sequence-main">
                  <label htmlFor={`react-sequence-element-${step.id}`}>{copy.settings.audioElement}</label>
                  <select
                    id={`react-sequence-element-${step.id}`}
                    value={step.element}
                    onChange={(event) => onChangeSequenceStep(step.id, {element: event.target.value as AudioSequenceElement})}
                  >
                    <option value="word">{copy.word}</option>
                    <option value="sentence">{copy.sentence}</option>
                  </select>
                  <small>{copy.settings.unavailableAudio}</small>
                </div>
                <div className="react-sequence-controls">
                  <div className="react-sequence-order" aria-label={copy.settings.moveStep(index + 1)}>
                    <button type="button" onClick={() => onMoveSequenceStep(step.id, "up")} disabled={index === 0} aria-label={copy.settings.moveStepUp(index + 1)}>↑</button>
                    <button type="button" onClick={() => onMoveSequenceStep(step.id, "down")} disabled={index === sequence.steps.length - 1} aria-label={copy.settings.moveStepDown(index + 1)}>↓</button>
                  </div>
                  <div className="react-sequence-stepper">
                    <span>{copy.settings.repeat}</span>
                    <span className="react-sequence-stepper-control">
                      <button type="button" onClick={() => onChangeSequenceStep(step.id, {repeatCount: Math.max(0, step.repeatCount - 1)})} disabled={step.repeatCount <= 0} aria-label={copy.settings.decreaseRepeat(index + 1)}>−</button>
                      <output aria-label={copy.settings.repeatCount(index + 1)}>{step.repeatCount}</output>
                      <button type="button" onClick={() => onChangeSequenceStep(step.id, {repeatCount: Math.min(9, step.repeatCount + 1)})} disabled={step.repeatCount >= 9} aria-label={copy.settings.increaseRepeat(index + 1)}>+</button>
                    </span>
                  </div>
                  <div className="react-sequence-field">
                    <span>{copy.settings.pauseAfter}</span>
                    <PauseAfterControl
                      stepIndex={index + 1}
                      value={step.pauseAfterMs}
                      onChange={(pauseAfterMs) => onChangeSequenceStep(step.id, {pauseAfterMs})}
                    />
                  </div>
                  <button type="button" className="react-sequence-remove" onClick={() => onRemoveSequenceStep(step.id)} disabled={sequence.steps.length <= 1} aria-label={`${copy.settings.remove} ${index + 1}`}>{copy.settings.remove}</button>
                </div>
              </div>
            ))}
          </div>

          <div className="react-sequence-add">
            <span>{copy.settings.addStep}</span>
            <button type="button" onClick={() => onAddSequenceStep("word")} disabled={sequence.steps.length >= MAX_AUDIO_SEQUENCE_STEPS}>{copy.settings.addWord}</button>
            <button type="button" onClick={() => onAddSequenceStep("sentence")} disabled={sequence.steps.length >= MAX_AUDIO_SEQUENCE_STEPS}>{copy.settings.addSentence}</button>
          </div>

          <div className="react-setting-copy">
            <span>{copy.settings.playbackMode}</span>
            <p>{copy.player.modeDescription(playbackRunMode)}</p>
          </div>
          <div className="react-setting-options react-playback-mode-options" role="group" aria-label={copy.settings.playbackMode}>
            {PLAYBACK_RUN_MODE_ORDER.map((mode) => (
              <button
                key={mode}
                type="button"
                className={playbackRunMode === mode ? "is-selected" : ""}
                onClick={() => onChangePlaybackRunMode(mode)}
                aria-pressed={playbackRunMode === mode}
              >
                {copy.player.modeLabel(mode)}
              </button>
            ))}
          </div>

          <div className="react-setting-copy">
            <span>{copy.settings.whenListEnds}</span>
            <p>{copy.settings.whenListEndsDescription}</p>
          </div>
          <div className="react-setting-options" role="group" aria-label={copy.settings.whenListEnds}>
            {PLAYBACK_END_BEHAVIOR_ORDER.map((behavior) => (
              <button
                key={behavior}
                type="button"
                className={playbackEndBehavior === behavior ? "is-selected" : ""}
                onClick={() => onChangePlaybackEndBehavior(behavior)}
                aria-pressed={playbackEndBehavior === behavior}
              >
                {copy.settings.endBehaviorLabel(behavior)}
              </button>
            ))}
          </div>

          <AccountControls state={accountState} />

          <button type="button" className="react-settings-reset" onClick={onReset}>{copy.settings.resetSequence}</button>
        </div>
      </section>
    </div>
  );
}
