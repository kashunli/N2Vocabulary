import { MAX_AUDIO_SEQUENCE_STEPS } from "./audioSequence.mjs";
import type {
  AudioSequenceConfig,
  AudioSequenceElement,
  AudioSequenceStep,
} from "./audioSequenceTypes";
import type { PlaybackMode, PlaybackRunMode } from "./playbackSettings";

interface PlaybackSettingsModalProps {
  playbackMode: PlaybackMode;
  playbackRunMode: PlaybackRunMode;
  sequence: AudioSequenceConfig;
  onChangePlaybackMode: (mode: PlaybackMode) => void;
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
  playbackMode,
  playbackRunMode,
  sequence,
  onChangePlaybackMode,
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
                    <option value="word">English word</option>
                    <option value="sentence">English sentence</option>
                  </select>
                  <small>Unavailable audio is skipped automatically.</small>
                </div>
                <div className="react-sequence-controls">
                  <div className="react-sequence-order" aria-label={`Move step ${index + 1}`}>
                    <button type="button" onClick={() => onMoveSequenceStep(step.id, "up")} disabled={index === 0} aria-label={`Move step ${index + 1} up`}>↑</button>
                    <button type="button" onClick={() => onMoveSequenceStep(step.id, "down")} disabled={index === sequence.steps.length - 1} aria-label={`Move step ${index + 1} down`}>↓</button>
                  </div>
                  <label className="react-sequence-field">
                    <span>Repeat</span>
                    <input
                      type="number"
                      min="0"
                      max="9"
                      step="1"
                      value={step.repeatCount}
                      aria-label={`Repeat step ${index + 1}`}
                      onChange={(event) => onChangeSequenceStep(step.id, {repeatCount: Number(event.target.value)})}
                    />
                  </label>
                  <label className="react-sequence-field">
                    <span>Pause after</span>
                    <span className="react-sequence-input-with-unit">
                      <input
                        type="number"
                        min="0"
                        max="3"
                        step="0.1"
                        value={pauseSeconds(step.pauseAfterMs)}
                        aria-label={`Pause after step ${index + 1}`}
                        onChange={(event) => onChangeSequenceStep(step.id, {pauseAfterMs: Math.round(Number(event.target.value) * 1000)})}
                      />
                      <span aria-hidden="true">s</span>
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
            <span>Audio included</span>
            <p>Filter the recipe when you want only one kind of clip during visible-list playback.</p>
          </div>
          <div className="react-setting-options" role="radiogroup" aria-label="Audio included">
            {(["words", "sentences", "both"] as PlaybackMode[]).map((mode) => <button type="button" key={mode} className={playbackMode === mode ? "is-selected" : ""} role="radio" aria-checked={playbackMode === mode} onClick={() => onChangePlaybackMode(mode)}>{mode === "words" ? "Words only" : mode === "sentences" ? "Sentences only" : "Use full recipe"}</button>)}
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
