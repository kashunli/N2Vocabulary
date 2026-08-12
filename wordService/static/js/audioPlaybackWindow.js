import { elements } from "./state.js";

export function clearScopePlaybackWindow() {
  elements.grid.querySelectorAll(".card.scope-previous, .card.scope-current, .card.scope-next").forEach(card => {
    card.classList.remove("scope-previous", "scope-current", "scope-next");
  });
}

export function setScopePlaybackWindow(entryId) {
  const cards = Array.from(elements.grid.querySelectorAll(".card"));
  const currentIndex = cards.findIndex(card => Number(card.dataset.id) === Number(entryId));
  cards.forEach((card, index) => {
    card.classList.toggle("scope-previous", currentIndex > 0 && index === currentIndex - 1);
    card.classList.toggle("scope-current", index === currentIndex);
    card.classList.toggle("scope-next", currentIndex >= 0 && index === currentIndex + 1);
  });
}
