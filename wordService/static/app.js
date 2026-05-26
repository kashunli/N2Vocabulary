const elements = {
  summaryMeta: document.getElementById("summary-meta"),
  unitSelect: document.getElementById("unit-select"),
  unitStrip: document.getElementById("unit-strip"),
  search: document.getElementById("search"),
  statePills: Array.from(document.querySelectorAll(".state-pill")),
  coverAll: document.getElementById("cover-all"),
  counter: document.getElementById("counter"),
  banner: document.getElementById("status-banner"),
  grid: document.getElementById("card-grid"),
  template: document.getElementById("card-template"),
  backdrop: document.getElementById("backdrop"),
  modalClose: document.querySelector(".modal-close"),
  modalMeta: document.getElementById("modal-meta"),
  modalTitle: document.getElementById("modal-title"),
  modalMeaning: document.getElementById("modal-meaning"),
  modalSentences: document.getElementById("modal-sentences"),
  modalExplanationWrap: document.getElementById("modal-explanation-wrap"),
  modalExplanation: document.getElementById("modal-explanation"),
};

const state = {
  units: [],
  selectedUnit: null,
  filterState: "all",
  search: "",
  currentAudio: null,
  currentEntries: [],
  detailEntry: null,
  coveredEntryIds: new Set(),
  generatingAudioKeys: new Set(),
};

function escapeHTML(value) {
  return String(value || "").replace(/[&<>"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

function inlineMarkdown(value) {
  // Keep Markdown rendering deliberately small and safe. We escape first, then
  // add only the formatting patterns the generated explanations commonly use.
  return escapeHTML(value)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>");
}

function markdownToHTML(value) {
  const blocks = [];
  let paragraph = [];
  let list = [];
  let listTag = "ul";

  function flushParagraph() {
    if (!paragraph.length) return;
    blocks.push(`<p>${paragraph.map(inlineMarkdown).join("<br>")}</p>`);
    paragraph = [];
  }

  function flushList() {
    if (!list.length) return;
    blocks.push(`<${listTag}>${list.map(item => `<li>${inlineMarkdown(item)}</li>`).join("")}</${listTag}>`);
    list = [];
    listTag = "ul";
  }

  String(value || "").replace(/\r\n/g, "\n").split("\n").forEach(rawLine => {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      flushList();
      return;
    }

    if (/^---+$/.test(line)) {
      flushParagraph();
      flushList();
      blocks.push("<hr>");
      return;
    }

    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      flushList();
      blocks.push(`<h${heading[1].length}>${inlineMarkdown(heading[2])}</h${heading[1].length}>`);
      return;
    }

    const bullet = line.match(/^[-*]\s+(.+)$/);
    if (bullet) {
      flushParagraph();
      if (listTag !== "ul") flushList();
      listTag = "ul";
      list.push(bullet[1]);
      return;
    }

    const numbered = line.match(/^\d+[.)]\s+(.+)$/);
    if (numbered) {
      flushParagraph();
      if (listTag !== "ol") flushList();
      listTag = "ol";
      list.push(numbered[1]);
      return;
    }

    flushList();
    paragraph.push(line);
  });

  flushParagraph();
  flushList();
  return blocks.join("");
}

function rubyOrPlain(kanji, reading) {
  if (!reading || reading === kanji) return escapeHTML(kanji);
  return `<ruby><rb>${escapeHTML(kanji)}</rb><rt>${escapeHTML(reading)}</rt></ruby>`;
}

function meaningHTML(entry) {
  const parts = [];
  if (entry.meaning_en) parts.push(`<span class="en">${escapeHTML(entry.meaning_en)}</span>`);
  if (entry.meaning_zh) parts.push(`<span class="zh">${escapeHTML(entry.meaning_zh)}</span>`);
  return parts.join(" · ");
}

function translationHTML(entry) {
  const parts = [];
  if (entry.sentence_translation_en) {
    parts.push(`<span class="en">${escapeHTML(entry.sentence_translation_en)}</span>`);
  }
  if (entry.sentence_translation_zh) {
    parts.push(`<span class="zh">${escapeHTML(entry.sentence_translation_zh)}</span>`);
  }
  return parts.join(" / ");
}

function setBanner(message) {
  if (!message) {
    elements.banner.classList.remove("show");
    elements.banner.textContent = "";
    return;
  }
  elements.banner.textContent = message;
  elements.banner.classList.add("show");
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.json();
}

async function loadSummary() {
  const summary = await fetchJson("/api/summary");
  elements.summaryMeta.innerHTML = [
    `<span>${summary.entries} entries</span>`,
    `<span>${summary.units} units</span>`,
    `<span>${summary.known} known</span>`,
    `<span>${summary.flagged} flagged</span>`,
    `<span>${summary.unmarked} unmarked</span>`,
  ].join("");
}

async function loadUnits() {
  const payload = await fetchJson("/api/units");
  state.units = payload.items || [];
  state.selectedUnit = state.selectedUnit || (state.units[0] && state.units[0].number);
  renderUnits();
}

function renderUnits() {
  elements.unitSelect.innerHTML = "";
  elements.unitStrip.innerHTML = "";

  state.units.forEach(unit => {
    const option = document.createElement("option");
    option.value = String(unit.number);
    option.textContent = `Unit ${String(unit.number).padStart(2, "0")} - ${unit.title}`;
    option.selected = unit.number === state.selectedUnit;
    elements.unitSelect.appendChild(option);

    const button = document.createElement("button");
    button.type = "button";
    button.className = "unit-tab";
    button.textContent = `Unit ${String(unit.number).padStart(2, "0")}`;
    button.classList.toggle("active", unit.number === state.selectedUnit);
    button.title = `${unit.title} - ${unit.entry_count} words`;
    button.addEventListener("click", () => selectUnit(unit.number));
    elements.unitStrip.appendChild(button);
  });
}

async function selectUnit(unitNumber) {
  state.selectedUnit = Number(unitNumber);
  renderUnits();
  await loadEntries();
}

async function loadEntries() {
  if (!state.selectedUnit) return;
  const params = new URLSearchParams({
    unit: String(state.selectedUnit),
    state: state.filterState,
    search: state.search,
  });
  const payload = await fetchJson(`/api/entries?${params.toString()}`);
  state.currentEntries = payload.items || [];
  renderCards();
}

function applyMarkClasses(card, mark) {
  card.classList.toggle("known", !!mark.known);
  card.classList.toggle("flagged", !!mark.flagged);
  card.querySelector(".icon-btn.known").classList.toggle("on", !!mark.known);
  card.querySelector(".icon-btn.flagged").classList.toggle("on", !!mark.flagged);
}

function applyCoverState(card, entry, covered) {
  // Covered cards keep the practice prompt visible, but hide the study answers:
  // furigana/readings, word meaning, sentence translations, and explanation access.
  card.classList.toggle("covered", covered);
  card.querySelector(".cover-button").textContent = covered ? "uncover" : "cover";
  card.querySelector(".card-kanji").innerHTML = covered
    ? escapeHTML(entry.kanji)
    : rubyOrPlain(entry.kanji, entry.reading);
  card.querySelector(".card-meaning").hidden = covered;
  card.querySelector(".card-sentence-translation").hidden = covered;

  const detailsButton = card.querySelector(".details-button");
  detailsButton.hidden = covered;
  detailsButton.disabled = covered;
}

function updateCoverAllButton() {
  const hasEntries = state.currentEntries.length > 0;
  const allVisibleCovered = hasEntries && state.currentEntries.every(entry => (
    state.coveredEntryIds.has(entry.entry_id)
  ));

  elements.coverAll.disabled = !hasEntries;
  elements.coverAll.textContent = allVisibleCovered ? "uncover all" : "cover all";
  elements.coverAll.setAttribute("aria-pressed", allVisibleCovered ? "true" : "false");
}

function renderCards() {
  elements.grid.innerHTML = "";
  if (!state.currentEntries.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No words match the current filters.";
    elements.grid.appendChild(empty);
    elements.counter.textContent = "showing 0";
    updateCoverAllButton();
    return;
  }

  state.currentEntries.forEach(entry => {
    const fragment = elements.template.content.cloneNode(true);
    const card = fragment.querySelector(".card");
    card.dataset.id = String(entry.entry_id);
    card.querySelector(".card-index").textContent = `#${String(entry.source_index).padStart(3, "0")} · Unit ${String(entry.unit.number).padStart(2, "0")}`;
    card.querySelector(".card-kanji").innerHTML = rubyOrPlain(entry.kanji, entry.reading);
    card.querySelector(".card-meaning").innerHTML = meaningHTML(entry);
    card.querySelector(".card-sentence").textContent = entry.sentence || "";
    card.querySelector(".card-sentence-translation").innerHTML = translationHTML(entry);

    wireAudioTarget(card.querySelector(".card-kanji"), entry.word_audio_url, "Play word audio");
    wireAudioTarget(card.querySelector(".card-sentence"), entry.sentence_audio_url, "Play sentence audio");

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
      openDetail(entry.entry_id).catch(showError);
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

    applyMarkClasses(card, entry.mark || {});
    applyCoverState(card, entry, state.coveredEntryIds.has(entry.entry_id));
    elements.grid.appendChild(fragment);
  });
  elements.counter.textContent = `showing ${state.currentEntries.length}`;
  updateCoverAllButton();
}

function wireAudioTarget(target, url, label) {
  target.dataset.src = url || "";
  target.classList.toggle("audio-target", !!url);
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

function playClip(target) {
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

async function toggleMark(entry, key, card) {
  const next = {
    known: !!(entry.mark && entry.mark.known),
    flagged: !!(entry.mark && entry.mark.flagged),
  };
  next[key] = !next[key];
  await fetchJson(`/api/marks/${entry.entry_id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(next),
  });
  entry.mark = {...entry.mark, ...next};
  applyMarkClasses(card, entry.mark);
  await loadSummary();
  await loadUnits();
}

async function openDetail(entryId) {
  const entry = await fetchJson(`/api/entries/${entryId}`);
  state.detailEntry = entry;
  elements.modalMeta.textContent = `#${String(entry.source_index).padStart(3, "0")} · Unit ${String(entry.unit.number).padStart(2, "0")}`;
  elements.modalTitle.innerHTML = rubyOrPlain(entry.kanji, entry.reading);
  wireAudioTarget(elements.modalTitle, entry.word_audio_url, "Play word audio");
  elements.modalMeaning.innerHTML = meaningHTML(entry);
  elements.modalSentences.innerHTML = sentenceRowsHTML(entry);
  wireModalSentenceRows(entry);

  if (entry.explanation_md) {
    elements.modalExplanation.innerHTML = markdownToHTML(entry.explanation_md);
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
    : [{position: 0, text: entry.sentence, translation_en: entry.sentence_translation_en, translation_zh: entry.sentence_translation_zh}];
  return examples.map(item => {
    const translation = [
      item.translation_en ? `<span class="en">${escapeHTML(item.translation_en)}</span>` : "",
      item.translation_zh ? `<span class="zh">${escapeHTML(item.translation_zh)}</span>` : "",
    ].filter(Boolean).join(" / ");
    return `
      <div class="sentence-row ${item.position === 0 ? "main" : ""}">
        ${item.position === 0 ? '<span class="badge">main</span>' : ""}
        <span>${escapeHTML(item.text)}</span>
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
      audio_url: entry.sentence_audio_url,
    };
    row.dataset.position = String(item.position);
    row.dataset.src = item.audio_url || "";

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
    const payload = await fetchJson(`/api/entries/${entry.entry_id}/examples/${item.position}/audio`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
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
  await fetchJson(`/api/marks/${entry.entry_id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(next),
  });
  closeDetail();
  await loadEntries();
  await loadSummary();
  await loadUnits();
}

function closeDetail() {
  elements.backdrop.classList.remove("open");
  elements.backdrop.setAttribute("aria-hidden", "true");
  if (state.currentAudio) {
    state.currentAudio.pause();
    if (state.currentAudio._target) state.currentAudio._target.classList.remove("playing");
  }
}

function showError(error) {
  console.error(error);
  setBanner(error.message || String(error));
}

function wireControls() {
  elements.unitSelect.addEventListener("change", event => {
    selectUnit(event.target.value).catch(showError);
  });
  elements.search.addEventListener("input", () => {
    state.search = elements.search.value.trim();
    loadEntries().catch(showError);
  });
  elements.statePills.forEach(pill => {
    pill.addEventListener("click", () => {
      state.filterState = pill.dataset.state || "all";
      elements.statePills.forEach(item => item.classList.toggle("active", item === pill));
      loadEntries().catch(showError);
    });
  });
  elements.coverAll.addEventListener("click", () => {
    const shouldCover = state.currentEntries.some(entry => !state.coveredEntryIds.has(entry.entry_id));
    state.currentEntries.forEach(entry => {
      if (shouldCover) {
        state.coveredEntryIds.add(entry.entry_id);
      } else {
        state.coveredEntryIds.delete(entry.entry_id);
      }
    });
    renderCards();
  });
  elements.modalClose.addEventListener("click", closeDetail);
  elements.backdrop.addEventListener("click", event => {
    if (event.target === elements.backdrop) closeDetail();
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && elements.backdrop.classList.contains("open")) closeDetail();
  });
}

async function init() {
  wireControls();
  await loadSummary();
  await loadUnits();
  await loadEntries();
}

init().catch(showError);
