import { fetchBooks, fetchEntries, fetchStarredSentences, fetchSummary, fetchUnits } from "./api.js";
import { renderCards } from "./cards.js";
import { resumeScopePlaybackFromSavedState, stopScopePlayback, updateScopePlaybackButton } from "./audio.js";
import { escapeHTML, exampleKey, unitLabel } from "./format.js";
import { renderStarredView } from "./starred.js";
import { elements, saveViewState, state } from "./state.js";
import { applyStudyMarks, summarizeStudyMarks } from "./studyState.js";

let entriesLoadToken = 0;

function currentBook() {
  return state.books.find(book => book.code === state.selectedBook) || {
    code: state.selectedBook,
    title: `${state.selectedBook} 語彙`,
  };
}

export async function loadBooks() {
  const payload = await fetchBooks();
  state.books = payload.items || [];
  if (!state.books.some(book => book.code === state.selectedBook)) {
    state.selectedBook = (state.books[0] && state.books[0].code) || "N2";
  }
  renderBooks();
}

export function renderBooks() {
  elements.bookSelect.innerHTML = "";
  state.books.forEach(book => {
    const option = document.createElement("option");
    option.value = book.code;
    option.textContent = `${book.code} - ${book.title}`;
    option.selected = book.code === state.selectedBook;
    elements.bookSelect.appendChild(option);
  });
  const book = currentBook();
  elements.pageTitle.textContent = "スタディウォール";
  document.title = `${book.code} Study Wall`;
}

export async function loadSummary() {
  const [summary, entriesPayload] = await Promise.all([fetchSummary(), fetchEntries(new URLSearchParams({state: "all"}))]);
  const active = summarizeStudyMarks(entriesPayload.items || []);
  const book = currentBook();
  elements.summaryMeta.innerHTML = [
    `<span>${escapeHTML(book.title)}</span>`,
    `<span>${summary.entries} entries</span>`,
    `<span>${summary.units} sections</span>`,
    `<span>${active.known} known</span>`,
    `<span>${active.flagged} flagged</span>`,
    `<span>${active.unmarked} unmarked</span>`,
  ].join("");
}

export async function loadUnits() {
  const payload = await fetchUnits();
  state.units = payload.items || [];
  const hasAllUnitSelection = state.selectedUnit === null;
  const savedUnitExists = state.units.some(unit => unit.number === state.selectedUnit);
  state.selectedUnit = hasAllUnitSelection
    ? null
    : (savedUnitExists ? state.selectedUnit : (state.units[0] && state.units[0].number));
  renderUnits();
}

export function renderUnits() {
  elements.unitSelect.innerHTML = "";
  elements.unitStrip.innerHTML = "";

  const allOption = document.createElement("option");
  allOption.value = "";
  allOption.textContent = "All sections";
  allOption.selected = state.selectedUnit === null;
  elements.unitSelect.appendChild(allOption);

  const allButton = document.createElement("button");
  allButton.type = "button";
  allButton.className = "unit-tab";
  allButton.textContent = "All";
  allButton.classList.toggle("active", state.selectedUnit === null);
  allButton.title = "Browse words from every section";
  allButton.addEventListener("click", () => selectUnit(null));
  elements.unitStrip.appendChild(allButton);

  state.units.forEach(unit => {
    const option = document.createElement("option");
    option.value = String(unit.number);
    option.textContent = `${unitLabel(unit)} - ${unit.entry_count} words`;
    option.selected = unit.number === state.selectedUnit;
    elements.unitSelect.appendChild(option);

    const button = document.createElement("button");
    button.type = "button";
    button.className = "unit-tab";
    button.textContent = unitLabel(unit);
    button.classList.toggle("active", unit.number === state.selectedUnit);
    button.title = `${unit.title} - ${unit.entry_count} words`;
    button.addEventListener("click", () => selectUnit(unit.number));
    elements.unitStrip.appendChild(button);
  });
}

export async function selectUnit(unitNumber) {
  const parsedUnit = Number(unitNumber);
  state.selectedUnit = Number.isFinite(parsedUnit) && parsedUnit > 0 ? parsedUnit : null;
  saveViewState();
  renderUnits();
  await loadEntries();
}

export async function loadEntries() {
  if (!state.units.length) return;
  const loadToken = entriesLoadToken + 1;
  entriesLoadToken = loadToken;
  stopScopePlayback({clearSaved: false});
  state.entriesLoading = true;
  updateScopePlaybackButton();
  const params = new URLSearchParams({
    state: "all",
    search: state.search,
  });
  // Omitting `unit` is the public API contract for all-unit listing/filtering.
  if (Number.isFinite(state.selectedUnit) && !state.search) {
    params.set("unit", String(state.selectedUnit));
  }
  try {
    const payload = await fetchEntries(params);
    if (loadToken !== entriesLoadToken) return;
    state.currentEntries = applyStudyMarks(payload.items || [], state.filterState);
    renderCards();
  } finally {
    if (loadToken === entriesLoadToken) {
      state.entriesLoading = false;
      updateScopePlaybackButton();
    }
  }
}

export async function loadStarredSentences() {
  const params = new URLSearchParams();
  if (state.starredScope === "unit" && state.selectedUnit) {
    params.set("unit", String(state.selectedUnit));
  }
  const payload = await fetchStarredSentences(params);
  state.starredSentences = payload.items || [];
  if (!state.starredSentences.some(item => exampleKey(item.entry_id, item.position) === state.selectedStarredKey)) {
    const first = state.starredSentences[0];
    state.selectedStarredKey = first ? exampleKey(first.entry_id, first.position) : null;
    saveViewState();
  }
  renderStarredView();
}

export async function showCardView() {
  state.view = "cards";
  saveViewState();
  elements.cardView.hidden = false;
  elements.starredView.hidden = true;
  elements.starredViewButton.classList.remove("active");
  elements.starredViewButton.setAttribute("aria-pressed", "false");
  await loadEntries();
  await resumeScopePlaybackFromSavedState(state.currentEntries);
}

export async function showStarredView(options = {}) {
  stopScopePlayback();
  state.view = "starred";
  if (options.resetScope) state.starredScope = "all";
  saveViewState();
  elements.cardView.hidden = true;
  elements.starredView.hidden = false;
  elements.starredViewButton.classList.add("active");
  elements.starredViewButton.setAttribute("aria-pressed", "true");
  await loadStarredSentences();
}
