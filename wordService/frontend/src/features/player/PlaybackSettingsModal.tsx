import type { PlaybackMode } from "./playbackSettings";

interface PlaybackSettingsModalProps {
  playbackMode: PlaybackMode;
  postSentenceSilence: number;
  postWordSilence: number;
  onChangePlaybackMode: (mode: PlaybackMode) => void;
  onChangePostSentenceSilence: (value: number) => void;
  onChangePostWordSilence: (value: number) => void;
  onClose: () => void;
  onReset: () => void;
}

export function PlaybackSettingsModal({
  playbackMode,
  postSentenceSilence,
  postWordSilence,
  onChangePlaybackMode,
  onChangePostSentenceSilence,
  onChangePostWordSilence,
  onClose,
  onReset,
}: PlaybackSettingsModalProps) {
  return (
    <div className="react-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="react-settings-modal" role="dialog" aria-modal="true" aria-labelledby="react-settings-title">
        <div className="react-settings-head"><div><span className="eyebrow">PLAYBACK</span><h2 id="react-settings-title">Playback settings</h2></div><button type="button" onClick={onClose} aria-label="Close playback settings">×</button></div>
        <div className="react-settings-body">
          <div className="react-setting-copy"><span>Playback</span><p>Choose what plays as the focused list advances.</p></div>
          <div className="react-setting-options" role="radiogroup" aria-label="Playback mode">
            {(["words", "sentences", "both"] as PlaybackMode[]).map((mode) => <button type="button" key={mode} className={playbackMode === mode ? "is-selected" : ""} role="radio" aria-checked={playbackMode === mode} onClick={() => onChangePlaybackMode(mode)}>{mode === "words" ? "Words only" : mode === "sentences" ? "Sentences only" : "Word + sentence"}</button>)}
          </div>
          <div className="react-setting-copy"><label htmlFor="react-post-word-silence">Silence after word</label><output htmlFor="react-post-word-silence">{postWordSilence} ms</output><p>Wait this long after a word clip before its sentence or the next word starts.</p></div>
          <input id="react-post-word-silence" type="range" min="0" max="3000" step="100" value={postWordSilence} onChange={(event) => onChangePostWordSilence(Number(event.target.value))} />
          <div className="react-setting-scale" aria-hidden="true"><span>None</span><span>3 seconds</span></div>
          <div className="react-setting-copy"><label htmlFor="react-post-sentence-silence">Silence after sentence</label><output htmlFor="react-post-sentence-silence">{postSentenceSilence} ms</output><p>Wait this long before the next word starts during visible-list playback.</p></div>
          <input id="react-post-sentence-silence" type="range" min="0" max="3000" step="100" value={postSentenceSilence} onChange={(event) => onChangePostSentenceSilence(Number(event.target.value))} />
          <div className="react-setting-scale" aria-hidden="true"><span>None</span><span>3 seconds</span></div>
          <button type="button" className="react-settings-reset" onClick={onReset}>Reset to defaults</button>
        </div>
      </section>
    </div>
  );
}
