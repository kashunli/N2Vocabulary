import { fetchEntry } from "./api.js";
import { cardMeaningHTML, detailExplanationHTML, escapeHTML, rubyOrPlain } from "./format.js";
import { toggleMark } from "./cards.js";
import { elements, showError, state } from "./state.js";

export function clearScopePlaybackWindow() {
  elements.grid.querySelectorAll(".card.scope-previous, .card.scope-current, .card.scope-next").forEach(card => {
    card.classList.remove("scope-previous", "scope-current", "scope-next");
  });
  syncRailCurrentPanel(state.currentEntries[0]?.entry_id);
}

const railDetailCache = new Map();

function panelMarkHTML(entry) {
  const knownOn = !!entry.mark?.known;
  const flaggedOn = !!entry.mark?.flagged;
  return `
    <div class="rail-panel-marks">
      <button type="button" class="icon-btn known" data-mark="known" aria-pressed="${knownOn ? "true" : "false"}">✓ Known</button>
      <button type="button" class="icon-btn flagged" data-mark="flagged" aria-pressed="${flaggedOn ? "true" : "false"}">⚑ Flag</button>
      <span class="rail-panel-index"></span>
    </div>
  `;
}

function panelSentenceHTML(entry) {
  const hasSentence = Boolean(entry.sentence && entry.sentence.trim());
  if (!hasSentence) return "";
  const en = entry.sentence_translation_en ? `<span class="en">${escapeHTML(entry.sentence_translation_en)}</span>` : "";
  const zh = entry.sentence_translation_zh ? `<span class="zh">${escapeHTML(entry.sentence_translation_zh)}</span>` : "";
  const translation = en || zh ? `<div class="rail-panel-sentence-translation">${en}${zh ? (en ? " / " : "") + zh : ""}</div>` : "";
  return `
    <div class="main-sentence-row rail-panel-sentence">
      <span class="rail-panel-sentence-text">${escapeHTML(entry.sentence)}</span>
      ${translation}
    </div>
  `;
}

function panelExplanationHTML(entry) {
  const md = entry.explanation_md;
  if (!md || !md.trim()) return "";
  return `
    <div class="section-label rail-panel-explain-label">Sentence explanation</div>
    <div class="rail-panel-explanation explanation">${detailExplanationHTML(entry)}</div>
  `;
}

function buildRailPanel(entry) {
  const panelEntry = railDetailCache.get(entry.entry_id) || entry;
  const article = document.createElement("article");
  article.className = "card rail-current-display";
  article.dataset.id = String(entry.entry_id);
  article.dataset.playbackPhase = state.scopePlaybackPhase || "idle";

  const marks = document.createElement("div");
  marks.innerHTML = panelMarkHTML(panelEntry);
  const marksRow = marks.firstElementChild;
  const indexSpan = marksRow.querySelector(".rail-panel-index");
  indexSpan.textContent = `${panelEntry.book_code} #${String(panelEntry.source_index || "").padStart(3, "0")}`;
  article.appendChild(marksRow);

  const word = document.createElement("div");
  word.className = "card-kanji";
  word.innerHTML = rubyOrPlain(panelEntry.kanji, panelEntry.reading);
  article.appendChild(word);

  const meaning = document.createElement("div");
  meaning.className = "card-meaning";
  meaning.innerHTML = cardMeaningHTML(panelEntry);
  article.appendChild(meaning);

  const sentenceWrap = document.createElement("div");
  sentenceWrap.innerHTML = panelSentenceHTML(panelEntry);
  const sentence = sentenceWrap.firstElementChild;
  if (sentence) article.appendChild(sentence);

  const explanationWrap = document.createElement("div");
  explanationWrap.innerHTML = panelExplanationHTML(panelEntry);
  while (explanationWrap.firstElementChild) {
    article.appendChild(explanationWrap.firstElementChild);
  }

  return article;
}

function wireRailPanelMarks(article, entry) {
  article.querySelectorAll("[data-mark]").forEach(button => {
    button.addEventListener("click", event => {
      event.stopPropagation();
      toggleMark(entry, button.dataset.mark, article).then(() => {
        const current = state.currentEntries.find(item => item.entry_id === entry.entry_id);
        if (current) {
          current.mark = entry.mark;
        }
        syncRailCurrentPanel(entry.entry_id);
      }).catch(showError);
    });
  });
}

export function syncRailCurrentPanel(entryId) {
  const panel = elements.railCurrentPanel;
  if (!panel) return;
  const numericId = Number(entryId);
  const entry = state.currentEntries.find(item => item.entry_id === numericId)
    || state.currentEntries[0];
  if (!entry) {
    panel.innerHTML = "";
    return;
  }

  // Refetch detail (for explanation_md) so the panel can show it once loaded.
  // Re-render is gated by the currently-displayed id, so a slow response for an
  // earlier card cannot overwrite the panel for a later one.
  if (!railDetailCache.has(entry.entry_id)) {
    fetchEntry(entry.entry_id).then(detail => {
      railDetailCache.set(entry.entry_id, detail);
      const displayedId = panel.querySelector(".rail-current-display")?.dataset.id;
      if (displayedId === String(entry.entry_id)) {
        panel.innerHTML = "";
        const article = buildRailPanel(entry);
        wireRailPanelMarks(article, entry);
        panel.appendChild(article);
      }
    }).catch(() => {});
  }

  panel.innerHTML = "";
  const article = buildRailPanel(entry);
  wireRailPanelMarks(article, entry);
  panel.appendChild(article);
}

export function setScopePlaybackWindow(entryId) {
  const cards = Array.from(elements.grid.querySelectorAll(".card"));
  const currentIndex = cards.findIndex(card => Number(card.dataset.id) === Number(entryId));
  cards.forEach((card, index) => {
    card.classList.toggle("scope-previous", currentIndex > 0 && index === currentIndex - 1);
    card.classList.toggle("scope-current", index === currentIndex);
    card.classList.toggle("scope-next", currentIndex >= 0 && index === currentIndex + 1);
  });
  syncRailCurrentPanel(entryId);
}
