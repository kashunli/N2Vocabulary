import { elements, saveRailLayoutSettings, state } from "./state.js";

function railLayoutBounds() {
  const layout = elements.railResizer?.parentElement;
  if (!layout) return null;
  const bounds = layout.getBoundingClientRect();
  return {
    layout,
    min: 220,
    max: Math.max(220, Math.min(620, Math.floor(bounds.width - 430 - 14))),
  };
}

function updateRailWidthUI() {
  const bounds = railLayoutBounds();
  if (!bounds) return;
  state.railListWidthPx = Math.min(bounds.max, Math.max(bounds.min, state.railListWidthPx));
  bounds.layout.style.setProperty("--rail-list-width", `${state.railListWidthPx}px`);
  elements.railResizer.setAttribute("aria-valuenow", String(state.railListWidthPx));
}

function setRailWidthFromPointer(clientX) {
  const bounds = railLayoutBounds();
  if (!bounds) return;
  state.railListWidthPx = Math.min(bounds.max, Math.max(bounds.min, Math.round(clientX - bounds.layout.getBoundingClientRect().left)));
  updateRailWidthUI();
}

export function wireRailResizer() {
  if (!elements.railResizer) return;
  updateRailWidthUI();
  let resizing = false;

  const stopResizing = () => {
    if (!resizing) return;
    resizing = false;
    document.body.classList.remove("is-resizing-rail");
    saveRailLayoutSettings();
  };

  elements.railResizer.addEventListener("pointerdown", event => {
    event.preventDefault();
    resizing = true;
    document.body.classList.add("is-resizing-rail");
    elements.railResizer.setPointerCapture?.(event.pointerId);
    setRailWidthFromPointer(event.clientX);
  });
  elements.railResizer.addEventListener("pointermove", event => {
    if (resizing) setRailWidthFromPointer(event.clientX);
  });
  elements.railResizer.addEventListener("pointerup", stopResizing);
  elements.railResizer.addEventListener("pointercancel", stopResizing);
  elements.railResizer.addEventListener("keydown", event => {
    const bounds = railLayoutBounds();
    if (!bounds) return;
    const step = event.shiftKey ? 50 : 20;
    if (event.key === "ArrowLeft") state.railListWidthPx -= step;
    else if (event.key === "ArrowRight") state.railListWidthPx += step;
    else if (event.key === "Home") state.railListWidthPx = bounds.min;
    else if (event.key === "End") state.railListWidthPx = bounds.max;
    else return;
    event.preventDefault();
    updateRailWidthUI();
    saveRailLayoutSettings();
  });
}
