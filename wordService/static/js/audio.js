import { generateEntryAudio, generateExampleAudio, exportUnitFlaggedAudio } from "./api.js";
import { unitLabel } from "./format.js";
import { clearSavedPlaybackState, elements, focusStudyEntry, readSavedPlaybackState, savePlaybackState, setBanner, showError, state, updateAudioExportButton } from "./state.js";
import { clearScopePlaybackWindow, setScopePlaybackWindow } from "./audioPlaybackWindow.js";
import { clipTargetForOffset } from "./audioPlaybackNavigation.js";
import { completeStudyReview, recordStudyCompleted } from "./studyState.js";

// Keep this export stable for cards.js while the implementation is organized
// into focused audio modules.
export { setScopePlaybackWindow };

let scopePlaybackToken = 0;
let scopeResumeWaiters = [];
function scopePlaybackIsActive() {
  return state.scopePlaybackStatus !== "idle";
}

function settleScopeResumeWaiters(token, resumed) {
  const remaining = [];
  scopeResumeWaiters.forEach(waiter => {
    if (token === undefined || waiter.token === token) {
      waiter.resolve(resumed);
    } else {
      remaining.push(waiter);
    }
  });
  scopeResumeWaiters = remaining;
}

function waitForScopeResume(token) {
  if (token !== scopePlaybackToken || state.scopePlaybackStatus === "idle") {
    return Promise.resolve(false);
  }
  if (state.scopePlaybackStatus === "playing") {
    return Promise.resolve(true);
  }
  return new Promise(resolve => scopeResumeWaiters.push({token, resolve}));
}

function waitAfterSentence(token) {
  if (token !== scopePlaybackToken) return Promise.resolve(false);
  return new Promise(resolve => {
    window.setTimeout(() => {
      resolve(token === scopePlaybackToken);
    }, state.postSentenceSilenceMs);
  });
}

function playbackPhase(target) {
  return target && target.classList.contains("card-kanji") ? "word" : "sentence";
}

function showPlaybackVisual(target, options = {}) {
  const {retainCard = false} = options;
  if (!target) return () => {};
  const card = target.closest(".card");
  if (!card) return () => {};

  const phase = playbackPhase(target);
  const progress = card.querySelector(".card-playback-progress");
  card.classList.add("scope-playing");
  card.dataset.playbackPhase = phase;
  // Three visual steps leave the line visibly in progress during both clips;
  // completion is represented by advancing to the next card.
  if (progress) progress.value = phase === "word" ? 1 : 2;

  return () => {
    if (!retainCard) {
      card.classList.remove("scope-playing", "scope-paused", "scope-replaying");
      delete card.dataset.playbackPhase;
      if (progress) progress.value = 0;
    }
  };
}

export function previewPlaybackVisual(target) {
  // This deterministic state is used only by the ?playback-preview URL during
  // visual regression checks; normal playback always drives the same helper.
  showPlaybackVisual(target);
}

function clearPlaybackVisuals() {
  elements.grid.querySelectorAll(".card.scope-playing").forEach(card => {
    card.classList.remove("scope-playing", "scope-paused", "scope-replaying");
    delete card.dataset.playbackPhase;
    const progress = card.querySelector(".card-playback-progress");
    if (progress) progress.value = 0;
    const label = card.querySelector(".card-playback-label");
    if (label) label.textContent = "Now playing";
  });
}

function updatePausedVisual(paused) {
  elements.grid.querySelectorAll(".card.scope-playing").forEach(card => {
    card.classList.toggle("scope-paused", paused);
    const label = card.querySelector(".card-playback-label");
    if (label) label.textContent = paused ? "Paused" : "Now playing";
  });
}

function showPreparingVisual(card) {
  clearPlaybackVisuals();
  card.classList.add("scope-playing");
  card.dataset.playbackPhase = "preparing";
  const label = card.querySelector(".card-playback-label");
  if (label) label.textContent = "Now playing";
}

function stopCurrentAudio() {
  if (!state.currentAudio) return;
  const audio = state.currentAudio;
  audio.pause();
  if (audio._target) {
    audio._target.classList.remove("playing");
  }
  state.currentAudio = null;
  if (audio._finish) {
    audio._finish(false);
  } else if (audio._clearVisual) {
    audio._clearVisual();
  }
}

function playTargetAndWait(target, token) {
  const src = target && target.dataset.src;
  if (!src || token !== scopePlaybackToken) return Promise.resolve(false);

  stopCurrentAudio();
  return new Promise(resolve => {
    const audio = new Audio(src);
    let settled = false;
    audio._target = target;
    state.currentAudio = audio;
    target.classList.add("playing");
    const clearVisual = showPlaybackVisual(target, {retainCard: true});
    audio._clearVisual = clearVisual;

    const finish = played => {
      if (settled) return;
      settled = true;
      target.classList.remove("playing");
      clearVisual();
      if (state.currentAudio === audio) state.currentAudio = null;
      resolve(played);
    };
    audio._finish = finish;
    audio.addEventListener("ended", () => finish(true), {once: true});
    audio.addEventListener("error", () => finish(false), {once: true});
    audio.play().catch(() => finish(false));
  });
}

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
  const cardEntryId = Number(target.closest(".card")?.dataset.id);
  if (Number.isFinite(cardEntryId)) {
    focusStudyEntry(cardEntryId, playbackPhase(target));
  }
  if (scopePlaybackIsActive()) {
    // Keyboard activation on card text should follow the same "start here"
    // rule as clicking the card while the visible queue is active.
    if (Number.isFinite(cardEntryId)) {
      playScopeFromEntry(cardEntryId).catch(showError);
      return;
    }
    stopScopePlayback();
  }
  stopCurrentAudio();
  const audio = new Audio(src);
  audio._target = target;
  target.classList.add("playing");
  const clearVisual = showPlaybackVisual(target);
  audio._clearVisual = clearVisual;
  audio.addEventListener("ended", () => {
    target.classList.remove("playing");
    clearVisual();
    if (state.currentAudio === audio) state.currentAudio = null;
  });
  audio.addEventListener("error", () => {
    target.classList.remove("playing");
    clearVisual();
    if (state.currentAudio === audio) state.currentAudio = null;
    setBanner(`Audio not found: ${src}`);
  });
  audio.play().catch(() => {
    target.classList.remove("playing");
    clearVisual();
    if (state.currentAudio === audio) state.currentAudio = null;
  });
  state.currentAudio = audio;
}

export async function ensureCardAudio(entry, card, options = {}) {
  const {announce = true, download = true} = options;
  const key = `${entry.entry_id}:card`;
  if (state.generatingAudioKeys.has(key)) return;
  state.generatingAudioKeys.add(key);
  card.classList.add("generating-audio");
  card.setAttribute("aria-busy", "true");
  try {
    const wordTarget = card.querySelector(".card-kanji");
    const sentenceTarget = card.querySelector(".main-sentence-row") || card.querySelector(".card-sentence");
    const sentencePosition = Number(sentenceTarget?.dataset.position || 0);
    const [wordPayload, sentencePayload] = await Promise.all([
      entry.word_audio_url
        ? Promise.resolve({audio_url: entry.word_audio_url})
        : generateEntryAudio(entry.entry_id),
      entry.sentence && entry.sentence.trim()
        ? (
            entry.sentence_audio_url
              ? Promise.resolve({audio_url: entry.sentence_audio_url})
              : generateExampleAudio(entry.entry_id, sentencePosition)
          )
        : Promise.resolve(null),
    ]);
    entry.word_audio_url = wordPayload.audio_url;
    if (sentencePayload) entry.sentence_audio_url = sentencePayload.audio_url;
    if (download) {
      await Promise.all(
        [entry.word_audio_url, entry.sentence_audio_url]
          .filter(Boolean)
          .map(downloadAudio)
      );
    }
    wireAudioTarget(wordTarget, entry.word_audio_url, "Play word audio");
    if (sentenceTarget) wireAudioTarget(sentenceTarget, entry.sentence_audio_url, "Play sentence audio");
    wireCardAudioPrepTarget(wordTarget, entry.word_audio_url, entry, card, "Generate word and sentence audio");
    if (sentenceTarget) wireCardAudioPrepTarget(sentenceTarget, entry.sentence_audio_url, entry, card, "Generate word and sentence audio");
    if (announce) setBanner("Word and sentence audio are ready.");
  } finally {
    state.generatingAudioKeys.delete(key);
    card.classList.remove("generating-audio");
    card.removeAttribute("aria-busy");
  }
}

export function updateScopePlaybackButton() {
  const hasEntries = state.view === "cards" && state.currentEntries.length > 0 && !state.entriesLoading;
  const status = state.scopePlaybackStatus;
  const active = status !== "idle";
  const paused = status === "paused";
  const currentEntry = state.currentEntries.find(entry => entry.entry_id === state.scopePlaybackEntryId);
  const saved = active ? null : readSavedPlaybackState();
  const hasSaved = saved && saved.scopePlaybackStatus !== "idle" && state.currentEntries.some(
    entry => entry.entry_id === saved.scopePlaybackEntryId
  );
  elements.scopePlayButton.disabled = !hasEntries;
  elements.scopePlayButton.classList.toggle("playing", status === "playing");
  elements.scopePlayButton.classList.toggle("paused", paused || (!active && hasSaved));
  elements.scopePlayButton.setAttribute("aria-pressed", (active || hasSaved) ? "true" : "false");
  elements.scopePlayButton.textContent = status === "playing"
      ? `pause · ${state.scopePlaybackPosition}/${state.scopePlaybackTotal}`
      : paused
        ? `resume · ${state.scopePlaybackPosition}/${state.scopePlaybackTotal}`
        : hasSaved
          ? `resume · ${saved.scopePlaybackPosition}/${saved.scopePlaybackTotal}`
          : "play visible";
  elements.scopePlayButton.title = !hasEntries
    ? "No visible vocabulary cards to play"
    : status === "playing"
        ? "Pause immediately"
        : paused
          ? "Resume from the same audio position"
        : hasSaved
          ? `Resume from where you left off (card ${saved.scopePlaybackPosition} of ${saved.scopePlaybackTotal})`
        : state.playbackMode === "words"
          ? "Play each visible word"
          : state.playbackMode === "sentences"
            ? "Play the main example sentence for each visible word"
          : "Play each visible word followed by its main example sentence";
  elements.grid.classList.toggle("scope-playback-active", active);
  elements.grid.classList.toggle("scope-playback-paused", paused);

  elements.playbackDock.hidden = state.view !== "cards";
  elements.playbackDock.classList.toggle("active", active);
  elements.playbackDock.classList.toggle("paused", paused);
  elements.playbackNowLabel.textContent = state.entriesLoading
    ? "Loading your list"
    : paused
      ? "Paused"
      : active
        ? `Playing ${state.scopePlaybackPhase}`
        : hasSaved
          ? "Paused earlier"
          : "Ready to play";
  elements.playbackNowDetail.textContent = state.entriesLoading
    ? "Playback will be ready when the visible list finishes loading."
    : currentEntry
      ? `${currentEntry.kanji} · ${state.scopePlaybackPosition} of ${state.scopePlaybackTotal}`
      : hasSaved
        ? "Press play to resume where you left off."
        : "Your visible list will move forward automatically.";
  elements.scopePlaybackCount.textContent = active
    ? `${state.scopePlaybackPosition} / ${state.scopePlaybackTotal}`
    : hasSaved
      ? `${saved.scopePlaybackPosition} / ${saved.scopePlaybackTotal}`
      : `0 / ${state.currentEntries.length}`;

  elements.scopeReplayButton.disabled = !active;
  elements.scopeReplayButton.querySelector("span").textContent = "Replay now";
  elements.scopePreviousButton.disabled = !active || !clipTargetForOffset(-1);
  elements.scopeNextButton.disabled = !active || !clipTargetForOffset(1);
  elements.scopeStopButton.disabled = !active;
  elements.scopePauseButton.disabled = !hasEntries;
  elements.scopePauseButton.querySelector("span").textContent = paused
      ? "Resume"
      : active
        ? "Pause"
        : "Start";
}

export function stopScopePlayback(options = {}) {
  const {announce = false, clearSaved = true} = options;
  scopePlaybackToken += 1;
  settleScopeResumeWaiters(undefined, false);
  const wasActive = scopePlaybackIsActive();
  state.scopePlaybackStatus = "idle";
  state.scopePlaybackPosition = 0;
  state.scopePlaybackTotal = 0;
  state.scopePlaybackEntryId = null;
  state.scopePlaybackPhase = "idle";
  stopCurrentAudio();
  clearPlaybackVisuals();
  clearScopePlaybackWindow();
  updateScopePlaybackButton();
  if (clearSaved) clearSavedPlaybackState();
  if (announce && wasActive) setBanner("Visible audio playback stopped.");
}

async function resumeScopePlayback() {
  if (state.scopePlaybackStatus !== "paused") return;
  if (state.currentAudio) {
    state.scopePlaybackStatus = "playing";
    updatePausedVisual(false);
    updateScopePlaybackButton();
    try {
      await state.currentAudio.play();
    } catch (error) {
      showError(error);
      return;
    }
    settleScopeResumeWaiters(scopePlaybackToken, true);
    setBanner(`Playing ${state.scopePlaybackPosition} of ${state.scopePlaybackTotal}.`);
    return;
  }
  // If the Audio object is gone (e.g. after a page reload), start fresh from
  // the saved position.
  const startIndex = Math.max(0, state.scopePlaybackPosition - 1);
  await startScopePlayback(startIndex, state.scopePlaybackPhase === "sentence" ? "sentence" : "word");
}

function pauseScopePlaybackImmediately() {
  if (state.scopePlaybackStatus !== "playing") return;
  state.scopePlaybackStatus = "paused";
  if (state.currentAudio) state.currentAudio.pause();
  updatePausedVisual(true);
  updateScopePlaybackButton();
  savePlaybackState();
  setBanner(`Paused ${state.scopePlaybackPosition} of ${state.scopePlaybackTotal}.`);
}

async function playEntryCycle(card, token, startPhase = "word") {
  const wordTarget = card.querySelector(".card-kanji");
  const sentenceTarget = card.querySelector(".main-sentence-row");
  let clipsPlayed = 0;
  let wordPlayed = false;
  let sentencePlayed = false;

  if (state.playbackMode !== "sentences" && startPhase !== "sentence") {
    state.scopePlaybackPhase = "word";
    focusStudyEntry(state.scopePlaybackEntryId, "word");
    updateScopePlaybackButton();
    savePlaybackState();
    if (await playTargetAndWait(wordTarget, token)) { clipsPlayed += 1; wordPlayed = true; }
    if (!await waitForScopeResume(token)) return {completed: false, clipsPlayed, fullCard: false};
  }

  if (state.playbackMode === "words") {
    return {completed: token === scopePlaybackToken, clipsPlayed, fullCard: false};
  }

  if (!sentenceTarget?.dataset.src) {
    return {completed: token === scopePlaybackToken, clipsPlayed, fullCard: wordPlayed};
  }

  state.scopePlaybackPhase = sentenceTarget?.dataset.src ? "sentence" : "card";
  if (state.scopePlaybackPhase === "sentence") {
    focusStudyEntry(state.scopePlaybackEntryId, "sentence");
  }
  updateScopePlaybackButton();
  savePlaybackState();
  sentencePlayed = await playTargetAndWait(sentenceTarget, token);
  if (sentencePlayed) {
    clipsPlayed += 1;
    // Keep the configured silence between this sentence and the next card's
    // word audio. A token check lets stop/restart invalidate the wait.
    if (!await waitAfterSentence(token)) return {completed: false, clipsPlayed, fullCard: false};
    if (!await waitForScopeResume(token)) return {completed: false, clipsPlayed, fullCard: false};
  }
  return {completed: token === scopePlaybackToken, clipsPlayed, fullCard: wordPlayed && sentencePlayed};
}

async function recordCompletedCard(entry, card) {
  if (state.filterState !== "review") {
    entry.mark = await recordStudyCompleted(entry);
    return;
  }
  const session = state.reviewSession;
  const expectedDueAt = session?.expectedDueAtByItemUuid[entry.item_uuid];
  if (!session || !expectedDueAt || session.completedByItemUuid[entry.item_uuid] || session.completingItemUuids.has(entry.item_uuid)) return;
  session.completingItemUuids.add(entry.item_uuid);
  try {
    const result = await completeStudyReview(entry, expectedDueAt);
    if (!result.completed || !result.card?.due_at) {
      setBanner("This review was already completed elsewhere. Re-enter Review to refresh the due list.");
      return;
    }
    entry.mark = result.card;
    entry.review_completed = true;
    session.completedByItemUuid[entry.item_uuid] = {reviewLevel: result.card.review_level, nextDueAt: result.card.due_at};
    card.classList.add("reviewed");
    const index = card.querySelector(".card-index");
    if (index && !index.textContent.includes("Reviewed")) index.textContent += " · Reviewed";
    setBanner(`${entry.kanji} reviewed. Level ${result.card.review_level}; next review ${new Date(result.card.due_at).toLocaleDateString()}.`);
  } catch (error) {
    session.completingItemUuids.delete(entry.item_uuid);
    throw error;
  }
}

async function startScopePlayback(startIndex = 0, initialPhase = "word") {
  if (state.entriesLoading) {
    setBanner("The visible list is still loading. Playback will be ready in a moment.");
    return;
  }
  // Snapshot the filtered list. If the learner changes scope, loadEntries()
  // stops this run before replacing the cards, so the queue never leaks into
  // a different book, section, mark state, or search result.
  const entries = [...state.currentEntries];
  if (!entries.length || startIndex < 0 || startIndex >= entries.length) return;

  // Invalidating the previous token lets an old queue unwind safely after its
  // current clip or lazy audio-generation request settles.
  const token = scopePlaybackToken + 1;
  scopePlaybackToken = token;
  settleScopeResumeWaiters(undefined, false);
  stopCurrentAudio();
  clearPlaybackVisuals();
  state.scopePlaybackStatus = "playing";
  state.scopePlaybackPosition = startIndex + 1;
  state.scopePlaybackTotal = entries.length;
  state.scopePlaybackEntryId = entries[startIndex].entry_id;
  state.scopePlaybackPhase = "preparing";
  updateScopePlaybackButton();

  let clipsPlayed = 0;
  let cardsVisited = 0;
  for (let index = startIndex; index < entries.length; index += 1) {
    if (token !== scopePlaybackToken) return;
    const entry = entries[index];
    const card = elements.grid.querySelector(`.card[data-id="${entry.entry_id}"]`);
    if (!card) continue;

    state.scopePlaybackPosition = index + 1;
    state.scopePlaybackEntryId = entry.entry_id;
    state.scopePlaybackPhase = "preparing";
    focusStudyEntry(entry.entry_id, state.playbackMode === "sentences" ? "sentence" : "word");
    cardsVisited += 1;
    setScopePlaybackWindow(entry.entry_id);
    showPreparingVisual(card);
    updateScopePlaybackButton();
    savePlaybackState();
    setBanner(`Playing ${index + 1} of ${entries.length}: ${entry.kanji}`);
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const bounds = card.getBoundingClientRect();
    const toolbarBottom = elements.scopePlayButton.closest(".controls")?.getBoundingClientRect().bottom || 0;
    const dockTop = elements.playbackDock.getBoundingClientRect().top || window.innerHeight;
    const visibleBottom = Math.min(window.innerHeight, dockTop);
    const availableTop = toolbarBottom + 12;
    const availableBottom = visibleBottom - 12;
    const centeredTop = availableTop + Math.max(0, (availableBottom - availableTop - bounds.height) / 2);
    const nextScrollTop = Math.max(0, window.scrollY + bounds.top - centeredTop);
    if (Math.abs(nextScrollTop - window.scrollY) > 1) {
      window.scrollTo({
        top: nextScrollTop,
        left: 0,
        behavior: reducedMotion ? "auto" : "smooth",
      });
    }

    if (state.playbackMode !== "words" && (!entry.word_audio_url || (entry.sentence && !entry.sentence_audio_url))) {
      try {
        await ensureCardAudio(entry, card, {announce: false, download: false});
      } catch (error) {
        console.error(`Could not prepare audio for entry ${entry.entry_id}`, error);
      }
    }
    if (!await waitForScopeResume(token)) return;

    const firstCycle = await playEntryCycle(card, token, index === startIndex ? initialPhase : "word");
    clipsPlayed += firstCycle.clipsPlayed;
    if (!firstCycle.completed) return;
    if (firstCycle.fullCard) await recordCompletedCard(entry, card);

    clearPlaybackVisuals();
  }

  if (token !== scopePlaybackToken) return;
  state.scopePlaybackStatus = "idle";
  state.scopePlaybackPosition = 0;
  state.scopePlaybackTotal = 0;
  state.scopePlaybackEntryId = null;
  state.scopePlaybackPhase = "idle";
  clearScopePlaybackWindow();
  updateScopePlaybackButton();
  clearSavedPlaybackState();
  const modeLabel = state.playbackMode === "words"
    ? "words"
    : state.playbackMode === "sentences"
      ? "sentences"
      : "word + sentence";
  setBanner(`Finished ${cardsVisited} visible entries (${clipsPlayed} ${modeLabel} audio clips).`);
}

export async function playScopeFromEntry(entryId) {
  const index = state.currentEntries.findIndex(entry => entry.entry_id === entryId);
  if (index < 0) return;
  await startScopePlayback(index);
}

export async function toggleScopePlayback() {
  if (state.scopePlaybackStatus === "playing") {
    pauseScopePlaybackImmediately();
    return;
  }
  if (state.scopePlaybackStatus === "paused") {
    await resumeScopePlayback();
    return;
  }
  // When idle, check for a saved position and resume from there.
  const saved = readSavedPlaybackState();
  if (saved && saved.scopePlaybackStatus !== "idle") {
    const index = state.currentEntries.findIndex(
      entry => entry.entry_id === saved.scopePlaybackEntryId
    );
    if (index >= 0) {
      await startScopePlayback(index, saved.scopePlaybackPhase === "sentence" ? "sentence" : "word");
      return;
    }
  }
  await startScopePlayback(0);
}

export async function replayScopeImmediately() {
  if (!scopePlaybackIsActive() || !state.scopePlaybackEntryId) return false;
  const currentIndex = Math.max(0, state.scopePlaybackPosition - 1);
  const phase = state.scopePlaybackPhase === "sentence" ? "sentence" : "word";
  setBanner(`Replaying the current ${phase} now.`);
  await startScopePlayback(currentIndex, phase);
  return true;
}

export async function moveScopePlayback(offset) {
  if (!scopePlaybackIsActive() || !Number.isFinite(offset) || offset === 0) return;
  const target = clipTargetForOffset(offset);
  if (!target) {
    if (offset > 0) {
      stopScopePlayback();
      setBanner("Finished the visible list.");
    }
    return;
  }
  if (offset < 0) {
    setBanner(`Playing the previous ${target.phase}.`);
  } else {
    setBanner(`Playing the next ${target.phase}.`);
  }
  await startScopePlayback(target.entryIndex, target.phase);
}

export async function downloadAudio(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Could not download audio (${response.status})`);
  await response.arrayBuffer();
}

export async function resumeScopePlaybackFromSavedState(entries) {
  const saved = readSavedPlaybackState();
  if (!saved || saved.scopePlaybackStatus === "idle") return false;
  if (!entries.length) return false;

  const entryIndex = entries.findIndex(
    entry => entry.entry_id === saved.scopePlaybackEntryId
  );
  if (entryIndex < 0) {
    clearSavedPlaybackState();
    return false;
  }

  // Restore the paused state so the UI shows playback dock controls.
  state.scopePlaybackStatus = "paused";
  state.scopePlaybackPosition = saved.scopePlaybackPosition || entryIndex + 1;
  state.scopePlaybackTotal = saved.scopePlaybackTotal || entries.length;
  state.scopePlaybackEntryId = saved.scopePlaybackEntryId;
  state.scopePlaybackPhase = saved.scopePlaybackPhase || "idle";
  focusStudyEntry(saved.scopePlaybackEntryId, saved.scopePlaybackPhase === "sentence" ? "sentence" : "word");

  // Show the card at the saved position as the current scope card.
  const card = elements.grid.querySelector(
    `.card[data-id="${saved.scopePlaybackEntryId}"]`
  );
  if (card) {
    const phase = saved.scopePlaybackPhase;
    card.classList.add("scope-playing", "scope-paused");
    card.dataset.playbackPhase = phase;
    const progress = card.querySelector(".card-playback-progress");
    if (progress) progress.value = phase === "word" ? 1 : phase === "sentence" ? 2 : 0;
    const label = card.querySelector(".card-playback-label");
    if (label) label.textContent = "Paused";
    setScopePlaybackWindow(saved.scopePlaybackEntryId);
  }

  updateScopePlaybackButton();
  return true;
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
