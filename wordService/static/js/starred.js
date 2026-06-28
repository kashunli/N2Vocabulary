import { wireAudioTarget } from "./audio.js";
import { toggleSentenceStar } from "./cards.js";
import { escapeHTML, exampleKey, exampleSourceLabel, exampleTranslationHTML, markdownToHTML, meaningHTML, rubyOrPlain, unitLabel } from "./format.js";
import { elements, saveViewState, showError, state } from "./state.js";

const callbacks = {
  loadStarredSentences: null,
  renderUnits: null,
  openDetail: null,
};

export function configureStarred(nextCallbacks) {
  Object.assign(callbacks, nextCallbacks);
}

function renderStarredUnits() {
  elements.starredUnitList.innerHTML = "";
  const allButton = document.createElement("button");
  allButton.type = "button";
  allButton.className = "starred-unit-button";
  allButton.classList.toggle("active", state.starredScope === "all");
  allButton.innerHTML = `<strong>All sections</strong><span>${state.starredSentences.length}</span>`;
  allButton.addEventListener("click", () => {
    state.starredScope = "all";
    saveViewState();
    callbacks.loadStarredSentences().catch(showError);
  });
  elements.starredUnitList.appendChild(allButton);

  state.units.forEach(unit => {
    const count = state.starredScope === "all"
      ? state.starredSentences.filter(item => item.unit.number === unit.number).length
      : "";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "starred-unit-button";
    button.classList.toggle("active", state.starredScope === "unit" && state.selectedUnit === unit.number);
    button.innerHTML = `<strong>${escapeHTML(unitLabel(unit))}</strong><span>${count}</span>`;
    button.title = unit.title;
    button.addEventListener("click", () => {
      state.selectedUnit = unit.number;
      state.starredScope = "unit";
      saveViewState();
      callbacks.renderUnits();
      callbacks.loadStarredSentences().catch(showError);
    });
    elements.starredUnitList.appendChild(button);
  });
}

export function renderStarredView() {
  renderStarredUnits();
  elements.starredListPanel.classList.toggle("empty", !state.starredSentences.length);
  elements.starredEmpty.hidden = !!state.starredSentences.length;
  elements.starredTitle.textContent = state.starredScope === "all"
    ? "All starred sentences"
    : `${unitLabel(state.units.find(unit => unit.number === state.selectedUnit))} starred`;
  elements.starredSubtitle.textContent = state.starredScope === "all"
    ? "Default review list across the whole vocabulary set"
    : "Only starred sentences from the selected section";
  elements.starredCount.textContent = `${state.starredSentences.length} shown`;
  elements.counter.textContent = `${state.starredSentences.length} starred sentences`;

  elements.starredList.innerHTML = "";
  state.starredSentences.forEach((item, index) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "starred-sentence-row";
    row.classList.toggle("selected", exampleKey(item.entry_id, item.position) === state.selectedStarredKey);
    row.dataset.key = exampleKey(item.entry_id, item.position);
    row.innerHTML = `
      <span class="starred-row-number">${String(index + 1).padStart(2, "0")}</span>
      <span class="starred-row-main">
        <span class="starred-jp">${escapeHTML(item.text)}</span>
        <span class="starred-translation">${exampleTranslationHTML(item)}</span>
        <span class="starred-source">${escapeHTML(exampleSourceLabel(item))}</span>
      </span>
      <span class="starred-row-star">★</span>
    `;
    row.addEventListener("click", () => {
      state.selectedStarredKey = row.dataset.key;
      saveViewState();
      renderStarredView();
    });
    elements.starredList.appendChild(row);
  });

  renderStarredDetail();
}

function renderStarredDetail() {
  const item = state.starredSentences.find(sentence => (
    exampleKey(sentence.entry_id, sentence.position) === state.selectedStarredKey
  ));
  if (!item) {
    elements.starredDetail.innerHTML = `
      <div class="starred-detail-empty">Pick a starred sentence to review it here.</div>
    `;
    return;
  }

  const translation = exampleTranslationHTML(item);
  elements.starredDetail.innerHTML = `
    <div class="starred-detail-head">
      <div class="starred-detail-word">${rubyOrPlain(item.word, item.reading)}</div>
      <div class="starred-detail-meta">${escapeHTML(unitLabel(item.unit))} · word #${item.source_index}</div>
    </div>
    <div class="starred-detail-body">
      <div class="starred-detail-sentence">
        <div class="starred-jp">${escapeHTML(item.text)}</div>
        ${translation ? `<div class="starred-translation">${translation}</div>` : ""}
      </div>
      <div class="starred-meaning">${meaningHTML({
        meaning_en: item.meaning_en,
        meaning_zh: item.meaning_zh,
      })}</div>
      <div>
        <div class="section-label">Sentence explanation</div>
        ${item.explanation_md
          ? `<div class="explanation">${markdownToHTML(item.explanation_md)}</div>`
          : `<div class="starred-missing-explanation">No sentence explanation yet. This slot is ready for the generated explanation field later.</div>`}
      </div>
      <div class="starred-detail-actions">
        <button class="details-button starred-word-detail" type="button">Open word detail</button>
        <button class="details-button starred-unstar" type="button">Unstar sentence</button>
      </div>
    </div>
  `;
  const sentenceTarget = elements.starredDetail.querySelector(".starred-detail-sentence");
  wireAudioTarget(sentenceTarget, item.audio_url, "Play sentence audio");
  elements.starredDetail.querySelector(".starred-word-detail").addEventListener("click", () => {
    callbacks.openDetail(item.entry_id).catch(showError);
  });
  elements.starredDetail.querySelector(".starred-unstar").addEventListener("click", () => {
    toggleSentenceStar(item.entry_id, item.position, false).catch(showError);
  });
}
