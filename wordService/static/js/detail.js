import { generateExampleAudio, fetchEntry, updateMark } from "./api.js";
import { playClip, wireAudioTarget } from "./audio.js";
import { applySentenceStarButton, toggleSentenceStar } from "./cards.js";
import { detailExplanationHTML, escapeHTML, exampleBadgeHTML, exampleTranslationHTML, meaningHTML, rubyOrPlain, unitLabel } from "./format.js";
import { elements, state, showError } from "./state.js";

const callbacks = {
  loadEntries: null,
  loadSummary: null,
  loadUnits: null,
};

export function configureDetail(nextCallbacks) {
  Object.assign(callbacks, nextCallbacks);
}

export async function openDetail(entryId) {
  const entry = await fetchEntry(entryId);
  state.detailEntry = entry;
  elements.modalMeta.textContent = `${entry.book_code} #${String(entry.source_index).padStart(3, "0")} · ${unitLabel(entry.unit)}`;
  elements.modalTitle.innerHTML = rubyOrPlain(entry.kanji, entry.reading);
  wireAudioTarget(elements.modalTitle, entry.word_audio_url, "Play word audio");
  elements.modalMeaning.innerHTML = meaningHTML(entry);
  elements.modalSentences.innerHTML = sentenceRowsHTML(entry);
  wireModalSentenceRows(entry);

  const explanationHTML = detailExplanationHTML(entry);
  if (explanationHTML) {
    elements.modalExplanation.innerHTML = explanationHTML;
    elements.modalExplanationWrap.style.display = "";
  } else {
    elements.modalExplanation.innerHTML = "";
    elements.modalExplanationWrap.style.display = "none";
  }

  const knownButton = document.querySelector(".modal-actions .icon-btn.known");
  const flaggedButton = document.querySelector(".modal-actions .icon-btn.flagged");
  knownButton.classList.toggle("on", !!entry.mark.known);
  flaggedButton.classList.toggle("on", !!entry.mark.flagged);
  knownButton.onclick = () => toggleModalMark("known").catch(showError);
  flaggedButton.onclick = () => toggleModalMark("flagged").catch(showError);

  elements.backdrop.classList.add("open");
  elements.backdrop.setAttribute("aria-hidden", "false");
  elements.modalClose.focus();
}

function sentenceRowsHTML(entry) {
  const examples = entry.examples && entry.examples.length
    ? entry.examples
    : [{position: 0, text: entry.sentence, translation_en: entry.sentence_translation_en, translation_zh: entry.sentence_translation_zh, starred: entry.sentence_starred}];
  return examples.map(item => {
    const translation = exampleTranslationHTML(item);
    const isMainRow = item.kind === "main_sentence" || (item.position === 0 && !item.category);
    return `
      <div class="sentence-row ${isMainRow ? "main" : ""}" data-position="${item.position}">
        <div class="sentence-row-head">
          ${exampleBadgeHTML(item)}
          ${item.source_book_code === "GWB_N2" ? `<span class="badge source-badge">GWB #${escapeHTML(item.source_index)}</span>` : ""}
          <button class="sentence-row-star" type="button" aria-pressed="${item.starred ? "true" : "false"}" title="Star sentence">${item.starred ? "★" : "☆"}</button>
        </div>
        <span class="sentence-text">${escapeHTML(item.text)}</span>
        ${item.reading ? `<span class="sentence-reading">${escapeHTML(item.reading)}</span>` : ""}
        ${translation ? `<span class="sentence-translation">${translation}</span>` : ""}
      </div>
    `;
  }).join("");
}

function wireModalSentenceRows(entry) {
  elements.modalSentences.querySelectorAll(".sentence-row").forEach((row, index) => {
    const examples = entry.examples && entry.examples.length ? entry.examples : [];
    const item = examples[index] || {
      position: 0,
      text: entry.sentence,
      reading: "",
      audio_url: entry.sentence_audio_url,
    };
    row.dataset.position = String(item.position);
    row.dataset.src = item.audio_url || "";
    const starButton = row.querySelector(".sentence-row-star");
    applySentenceStarButton(starButton, !!item.starred);
    starButton.addEventListener("click", event => {
      event.stopPropagation();
      toggleSentenceStar(entry.entry_id, item.position, !item.starred).then(starred => {
        item.starred = starred;
        if (item.position === 0) {
          entry.sentence_starred = starred;
        }
        applySentenceStarButton(starButton, starred);
        const cardEntry = state.currentEntries.find(current => current.entry_id === entry.entry_id);
        if (cardEntry && item.position === 0) {
          cardEntry.sentence_starred = starred;
          const card = elements.grid.querySelector(`.card[data-id="${entry.entry_id}"]`);
          if (card) applySentenceStarButton(card.querySelector(".sentence-star"), starred);
        }
      }).catch(showError);
    });

    if (item.audio_url) {
      row.classList.remove("generatable", "generating");
      wireAudioTarget(row, item.audio_url, "Play sentence audio");
      return;
    }

    row.classList.add("generatable");
    row.classList.remove("playing", "generating");
    row.setAttribute("role", "button");
    row.setAttribute("tabindex", "0");
    row.setAttribute("aria-label", "Generate sentence audio");
    row.onclick = event => {
      event.stopPropagation();
      generateSentenceAudio(entry, item, row).catch(showError);
    };
    row.onkeydown = event => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      event.stopPropagation();
      generateSentenceAudio(entry, item, row).catch(showError);
    };
  });
}

async function generateSentenceAudio(entry, item, row) {
  const key = `${entry.entry_id}:${item.position}`;
  if (state.generatingAudioKeys.has(key)) return;
  state.generatingAudioKeys.add(key);
  row.classList.add("generating");
  row.setAttribute("aria-busy", "true");
  try {
    const payload = await generateExampleAudio(entry.entry_id, item.position);
    item.audio_url = payload.audio_url;
    if (item.position === 0) {
      entry.sentence_audio_url = payload.audio_url;
    }
    row.classList.remove("generatable", "generating");
    row.removeAttribute("aria-busy");
    wireAudioTarget(row, payload.audio_url, "Play sentence audio");
    playClip(row);
  } finally {
    state.generatingAudioKeys.delete(key);
    row.classList.remove("generating");
    row.removeAttribute("aria-busy");
  }
}

async function toggleModalMark(key) {
  if (!state.detailEntry) return;
  const entry = state.detailEntry;
  const next = {
    known: !!entry.mark.known,
    flagged: !!entry.mark.flagged,
  };
  next[key] = !next[key];
  await updateMark(entry.entry_id, next);
  closeDetail();
  await callbacks.loadEntries();
  await callbacks.loadSummary();
  await callbacks.loadUnits();
}

export function closeDetail() {
  elements.backdrop.classList.remove("open");
  elements.backdrop.setAttribute("aria-hidden", "true");
  if (state.currentAudio) {
    state.currentAudio.pause();
    if (state.currentAudio._target) state.currentAudio._target.classList.remove("playing");
  }
}
