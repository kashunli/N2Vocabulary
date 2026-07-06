import { updateMark, updateExampleStar } from "./api.js";
import { ensureCardAudio, playClip, wireAudioTarget, wireCardAudioPrepTarget } from "./audio.js";
import { cardMeaningHTML, escapeHTML, exampleCategoryBadgeHTML, exampleTranslationHTML, rubyOrPlain, unitLabel } from "./format.js";
import { elements, state, showError, updateAudioExportButton } from "./state.js";

const callbacks = {
  loadSummary: null,
  loadUnits: null,
  loadStarredSentences: null,
  openDetail: null,
};

export function configureCards(nextCallbacks) {
  Object.assign(callbacks, nextCallbacks);
}

export function applyMarkClasses(card, mark) {
  card.classList.toggle("known", !!mark.known);
  card.classList.toggle("flagged", !!mark.flagged);
  card.querySelector(".icon-btn.known").classList.toggle("on", !!mark.known);
  card.querySelector(".icon-btn.flagged").classList.toggle("on", !!mark.flagged);
}

export function applySentenceStarButton(button, starred) {
  button.classList.toggle("on", !!starred);
  button.textContent = starred ? "★" : "☆";
  button.setAttribute("aria-pressed", starred ? "true" : "false");
}

export function applyCoverState(card, entry, covered) {
  // Covered cards keep the practice prompt visible, but hide the study answers:
  // furigana/readings, word meaning, sentence translations, and explanation access.
  card.classList.toggle("covered", covered);
  card.querySelector(".cover-button").textContent = covered ? "uncover" : "cover";
  card.querySelector(".card-kanji").innerHTML = covered
    ? escapeHTML(entry.kanji)
    : rubyOrPlain(entry.kanji, entry.reading);
  card.querySelector(".card-meaning").hidden = covered;
  const legacyTranslation = card.querySelector(".card-sentence-translation");
  if (legacyTranslation) legacyTranslation.hidden = covered;
  card.querySelectorAll(".card-example-row .card-example-translation").forEach(node => {
    node.hidden = covered;
  });
  const searchMatches = card.querySelector(".card-search-matches");
  if (searchMatches) {
    searchMatches.hidden = covered;
  }

  const detailsButton = card.querySelector(".details-button");
  detailsButton.hidden = covered;
  detailsButton.disabled = covered;
}

export function updateCoverAllButton() {
  const hasEntries = state.currentEntries.length > 0;
  const allVisibleCovered = hasEntries && state.currentEntries.every(entry => (
    state.coveredEntryIds.has(entry.entry_id)
  ));

  elements.coverAll.disabled = !hasEntries;
  elements.coverAll.textContent = allVisibleCovered ? "uncover all" : "cover all";
  elements.coverAll.setAttribute("aria-pressed", allVisibleCovered ? "true" : "false");
}

export function renderCards() {
  elements.grid.innerHTML = "";
  if (!state.currentEntries.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No words match the current filters.";
    elements.grid.appendChild(empty);
    elements.counter.textContent = "showing 0";
    updateCoverAllButton();
    updateAudioExportButton();
    return;
  }

  state.currentEntries.forEach(entry => {
    const fragment = elements.template.content.cloneNode(true);
    const card = fragment.querySelector(".card");
    card.dataset.id = String(entry.entry_id);
    card.querySelector(".card-index").textContent = `${entry.book_code} #${String(entry.source_index).padStart(3, "0")} · ${unitLabel(entry.unit)}`;
    card.querySelector(".card-kanji").innerHTML = rubyOrPlain(entry.kanji, entry.reading);
    card.querySelector(".card-meaning").innerHTML = cardMeaningHTML(entry);
    renderCardSentences(card, entry);
    renderSearchMatches(card, entry);

    const wordTarget = card.querySelector(".card-kanji");
    const sentenceTarget = card.querySelector(".main-sentence-row");
    wireAudioTarget(wordTarget, entry.word_audio_url, "Play word audio");
    if (sentenceTarget) wireAudioTarget(sentenceTarget, entry.sentence_audio_url, "Play sentence audio");
    wireCardAudioPrepTarget(wordTarget, entry.word_audio_url, entry, card, "Generate word and sentence audio");
    if (sentenceTarget) wireCardAudioPrepTarget(sentenceTarget, entry.sentence_audio_url, entry, card, "Generate word and sentence audio");

    const sentenceStar = card.querySelector(".icon-btn.sentence-star");
    applySentenceStarButton(sentenceStar, entry.sentence_starred);
    sentenceStar.addEventListener("click", event => {
      event.stopPropagation();
      toggleSentenceStar(entry.entry_id, 0, !entry.sentence_starred).then(starred => {
        entry.sentence_starred = starred;
        applySentenceStarButton(sentenceStar, starred);
      }).catch(showError);
    });
    card.querySelector(".icon-btn.known").addEventListener("click", event => {
      event.stopPropagation();
      toggleMark(entry, "known", card).catch(showError);
    });
    card.querySelector(".icon-btn.flagged").addEventListener("click", event => {
      event.stopPropagation();
      toggleMark(entry, "flagged", card).catch(showError);
    });
    card.querySelector(".details-button").addEventListener("click", event => {
      event.stopPropagation();
      callbacks.openDetail(entry.entry_id).catch(showError);
    });
    card.querySelector(".cover-button").addEventListener("click", event => {
      event.stopPropagation();
      const covered = !state.coveredEntryIds.has(entry.entry_id);
      if (covered) {
        state.coveredEntryIds.add(entry.entry_id);
      } else {
        state.coveredEntryIds.delete(entry.entry_id);
      }
      applyCoverState(card, entry, covered);
      updateCoverAllButton();
    });
    card.addEventListener("click", event => {
      if (event.target.closest("button")) return;
      if (event.target.closest(".audio-target, [data-card-audio-prep]")) return;

      const wordTarget = card.querySelector(".card-kanji");
      if (entry.word_audio_url) {
        event.stopPropagation();
        playClip(wordTarget);
        return;
      }

      ensureCardAudio(entry, card)
        .then(() => {
          if (entry.word_audio_url) playClip(wordTarget);
        })
        .catch(showError);
    }, {capture: true});

    applyMarkClasses(card, entry.mark || {});
    applyCoverState(card, entry, state.coveredEntryIds.has(entry.entry_id));
    elements.grid.appendChild(fragment);
  });
  const scope = state.selectedUnit === null || state.search ? " across all sections" : "";
  elements.counter.textContent = `showing ${state.currentEntries.length}${scope}`;
  updateCoverAllButton();
  updateAudioExportButton();
}

function renderCardSentences(card, entry) {
  const examples = (entry.examples || []).filter(item => item.text);
  const mainExample = examples.find(item => item.position === 0);
  const extraExamples = examples.filter(item => item.position > 0);
  const sentenceItems = [];
  if (mainExample) {
    sentenceItems.push({...mainExample, isMain: true});
  } else if (entry.sentence) {
    sentenceItems.push({
      position: 0,
      text: entry.sentence,
      translation_en: entry.sentence_translation_en,
      translation_zh: entry.sentence_translation_zh,
      audio_url: entry.sentence_audio_url,
      isMain: true,
    });
  }
  sentenceItems.push(...extraExamples);

  const wrap = document.createElement("div");
  wrap.className = "card-examples";

  sentenceItems.forEach(item => {
    const row = document.createElement("div");
    row.className = item.isMain ? "card-example-row main-sentence-row" : "card-example-row";
    row.dataset.position = String(item.position);
    row.dataset.src = item.audio_url || "";

    const categoryBadge = exampleCategoryBadgeHTML(item);
    if (categoryBadge) {
      const head = document.createElement("div");
      head.className = "card-example-head";
      head.innerHTML = categoryBadge;
      row.appendChild(head);
    }

    const text = document.createElement("span");
    text.className = "card-example-text";
    text.textContent = item.text || "";
    row.appendChild(text);

    if (item.reading) {
      const reading = document.createElement("span");
      reading.className = "card-example-reading";
      reading.textContent = item.reading;
      row.appendChild(reading);
    }

    const translation = exampleTranslationHTML(item);
    if (translation) {
      const translationNode = document.createElement("span");
      translationNode.className = "card-example-translation";
      translationNode.innerHTML = translation;
      row.appendChild(translationNode);
    }

    wrap.appendChild(row);
    wireAudioTarget(row, item.audio_url, item.isMain ? "Play sentence audio" : "Play example audio");
  });

  card.querySelector(".card-meaning").after(wrap);
  card.querySelector(".card-sentence")?.remove();
  card.querySelector(".card-sentence-translation")?.remove();
}

function renderSearchMatches(card, entry) {
  const matches = state.search ? (entry.search_matches || []) : [];
  if (!matches.length) return;

  const wrap = document.createElement("div");
  wrap.className = "card-search-matches";
  wrap.innerHTML = `<div class="search-match-label">Matching sentences</div>`;

  matches.forEach(item => {
    const row = document.createElement("div");
    row.className = "search-match-row";
    row.dataset.src = item.audio_url || "";

    const sentence = document.createElement("span");
    sentence.className = "search-match-text";
    sentence.textContent = item.text || "";
    row.appendChild(sentence);

    if (item.reading) {
      const reading = document.createElement("span");
      reading.className = "search-match-reading";
      reading.textContent = item.reading;
      row.appendChild(reading);
    }

    const translation = [
      item.translation_en ? `<span class="en">${escapeHTML(item.translation_en)}</span>` : "",
      item.translation_zh ? `<span class="zh">${escapeHTML(item.translation_zh)}</span>` : "",
    ].filter(Boolean).join(" / ");
    if (translation) {
      const translationNode = document.createElement("span");
      translationNode.className = "search-match-translation";
      translationNode.innerHTML = translation;
      row.appendChild(translationNode);
    }

    wrap.appendChild(row);
    wireAudioTarget(row, item.audio_url, "Play matching sentence audio");
  });

  const insertionPoint =
    card.querySelector(".card-examples")
    || card.querySelector(".card-meaning")
    || card.querySelector(".card-kanji");
  if (insertionPoint) insertionPoint.after(wrap);
}

export async function toggleMark(entry, key, card) {
  const next = {
    known: !!(entry.mark && entry.mark.known),
    flagged: !!(entry.mark && entry.mark.flagged),
  };
  next[key] = !next[key];
  await updateMark(entry.entry_id, next);
  entry.mark = {...entry.mark, ...next};
  applyMarkClasses(card, entry.mark);
  await callbacks.loadSummary();
  await callbacks.loadUnits();
}

export async function toggleSentenceStar(entryId, position, starred) {
  const payload = await updateExampleStar(entryId, position, starred);
  if (state.view === "starred") {
    await callbacks.loadStarredSentences();
  }
  return !!payload.starred;
}
