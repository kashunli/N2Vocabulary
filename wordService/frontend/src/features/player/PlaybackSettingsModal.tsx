import { MAX_AUDIO_SEQUENCE_STEPS } from "./audioSequence.mjs";
import type {
  AudioSequenceConfig,
  AudioSequenceElement,
  AudioSequenceStep,
} from "./audioSequenceTypes";
import type { PlaybackRunMode } from "./playbackSettings";

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
                  <label className="react-sequence-field">
                    <span>Pause after</span>
                    <span className="react-sequence-slider-row">
                      <input
                        type="range"
                        min="0"
                        max="3"
                        step="0.1"
                        value={step.pauseAfterMs / 1000}
                        aria-label={`Pause after step ${index + 1}`}
                        onChange={(event) => onChangeSequenceStep(step.id, {pauseAfterMs: Math.round(Number(event.target.value) * 1000)})}
                      />
                      <output>{pauseSeconds(step.pauseAfterMs)}s</output>
                    </span>
                  </label>
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
            <p>{playbackRunMode === "single" ? "Stop after the focused occurrence." : "Continue through every available row, then move to the next entry."}</p>
          </div>
          <button type="button" className="react-sequence-run-mode" onClick={onTogglePlaybackRunMode} aria-pressed={playbackRunMode === "consecutive"}>
            {playbackRunMode === "single" ? "Single occurrence" : "Continue through list"}
          </button>

          <button type="button" className="react-settings-reset" onClick={onReset}>Reset sequence</button>
        </div>
      </section>
    </div>
  );
}
