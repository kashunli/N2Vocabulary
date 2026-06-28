import { generateEntryAudio, generateExampleAudio, exportUnitFlaggedAudio } from "./api.js";
import { unitLabel } from "./format.js";
import { state, setBanner, showError, updateAudioExportButton } from "./state.js";

export function wireAudioTarget(target, url, label) {
  target.dataset.src = url || "";
  target.classList.toggle("audio-target", !!url);
  target.classList.remove("audio-pending-target");
  delete target.dataset.cardAudioPrep;
  target.classList.remove("playing");

  if (!url) {
    target.removeAttribute("role");
    target.removeAttribute("tabindex");
    target.removeAttribute("aria-label");
    target.onclick = null;
    target.onkeydown = null;
    return;
  }

  // The text itself is the control now, so keep it keyboard-friendly without
  // reintroducing obvious play buttons into the card layout.
  target.setAttribute("role", "button");
  target.setAttribute("tabindex", "0");
  target.setAttribute("aria-label", label);
  target.onclick = event => {
    event.stopPropagation();
    playClip(target);
  };
  target.onkeydown = event => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    event.stopPropagation();
    playClip(target);
  };
}

export function wireCardAudioPrepTarget(target, url, entry, card, label) {
  if (url) return;
  if (!target.textContent.trim()) return;

  // Missing card audio is still actionable: the first click generates and
  // downloads both clips. Mark the visible text so the cursor matches that
  // lazy-generation behavior before the audio URLs exist.
  target.classList.add("audio-pending-target");
  target.dataset.cardAudioPrep = "true";
  target.setAttribute("role", "button");
  target.setAttribute("tabindex", "0");
  target.setAttribute("aria-label", label);
  target.onclick = event => {
    event.stopPropagation();
    ensureCardAudio(entry, card).then(() => playClip(target)).catch(showError);
  };
  target.onkeydown = event => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    event.stopPropagation();
    ensureCardAudio(entry, card).then(() => playClip(target)).catch(showError);
  };
}

export function playClip(target) {
  const src = target.dataset.src;
  if (!src) return;
  if (state.currentAudio) {
    state.currentAudio.pause();
    if (state.currentAudio._target) state.currentAudio._target.classList.remove("playing");
  }
  const audio = new Audio(src);
  audio._target = target;
  target.classList.add("playing");
  audio.addEventListener("ended", () => target.classList.remove("playing"));
  audio.addEventListener("error", () => {
    target.classList.remove("playing");
    setBanner(`Audio not found: ${src}`);
  });
  audio.play().catch(() => target.classList.remove("playing"));
  state.currentAudio = audio;
}

export async function ensureCardAudio(entry, card) {
  const key = `${entry.entry_id}:card`;
  if (state.generatingAudioKeys.has(key)) return;
  state.generatingAudioKeys.add(key);
  card.classList.add("generating-audio");
  card.setAttribute("aria-busy", "true");
  try {
    const [wordPayload, sentencePayload] = await Promise.all([
      entry.word_audio_url
        ? Promise.resolve({audio_url: entry.word_audio_url})
        : generateEntryAudio(entry.entry_id),
      entry.sentence && entry.sentence.trim()
        ? (
            entry.sentence_audio_url
              ? Promise.resolve({audio_url: entry.sentence_audio_url})
              : generateExampleAudio(entry.entry_id, 0)
          )
        : Promise.resolve(null),
    ]);
    entry.word_audio_url = wordPayload.audio_url;
    if (sentencePayload) entry.sentence_audio_url = sentencePayload.audio_url;
    await Promise.all(
      [entry.word_audio_url, entry.sentence_audio_url]
        .filter(Boolean)
        .map(downloadAudio)
    );
    const wordTarget = card.querySelector(".card-kanji");
    const sentenceTarget = card.querySelector(".main-sentence-row") || card.querySelector(".card-sentence");
    wireAudioTarget(wordTarget, entry.word_audio_url, "Play word audio");
    if (sentenceTarget) wireAudioTarget(sentenceTarget, entry.sentence_audio_url, "Play sentence audio");
    wireCardAudioPrepTarget(wordTarget, entry.word_audio_url, entry, card, "Generate word and sentence audio");
    if (sentenceTarget) wireCardAudioPrepTarget(sentenceTarget, entry.sentence_audio_url, entry, card, "Generate word and sentence audio");
    setBanner("Word and sentence audio are ready.");
  } finally {
    state.generatingAudioKeys.delete(key);
    card.classList.remove("generating-audio");
    card.removeAttribute("aria-busy");
  }
}

export async function downloadAudio(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Could not download audio (${response.status})`);
  await response.arrayBuffer();
}

export async function exportFlaggedAudio() {
  if (!Number.isFinite(state.selectedUnit) || state.exportingAudio) return;
  state.exportingAudio = true;
  updateAudioExportButton();
  setBanner("");
  try {
    const payload = await exportUnitFlaggedAudio(state.selectedUnit);
    const link = document.createElement("a");
    link.href = payload.audio_url;
    link.download = payload.file_name || "";
    document.body.appendChild(link);
    link.click();
    link.remove();
    const unit = state.units.find(item => item.number === payload.unit);
    setBanner(`Exported ${payload.word_count} flagged words from ${unitLabel(unit)}.`);
  } finally {
    state.exportingAudio = false;
    updateAudioExportButton();
  }
}
