#!/usr/bin/env python3
"""
build_word_cards.py — Generate compact card-grid HTML pages for N2 vocabulary.

Reads:  ../output/n2vocab.sqlite
Writes: words/cards/
          index.html
          unit_01.html .. unit_13.html

Each card shows kanji+ruby, glosses, the `sentence` field, two play buttons
(word + sentence audio), and two toggle buttons (known / flagged).
State is persisted to output/n2vocab.sqlite via marks_server.py, with a
localStorage fallback if the server is offline.

Run from any cwd:
    python wordsAndExerciseInHtml/build_word_cards.py
"""

import html
import json
import re
import sys
from collections import OrderedDict, defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
OUT_DIR = SCRIPT_DIR / "words" / "cards"
MARKS_SERVER_URL = "http://127.0.0.1:8766"

# Reuse the markdown→HTML helper from the existing long-page builder.
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(PROJECT_ROOT))
from build_words import explanation_html as _md_explanation_html  # noqa: E402
from db import DB_PATH, load_entries  # noqa: E402

# Cards live at words/cards/unit_XX.html → audio clips at <project_root>/clips/...
CLIP_PREFIX_FROM_CARDS = "../../../"  # words/cards/ → project root
# Fallback long-form page (kept for printing / external linking):
LONG_PAGE_HREF_FMT = "../by_unit/unit_{num:02d}.html#w{idx}"


CSS = r"""
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --paper: #faf9f6;
  --paper2: #f3f1ec;
  --ink: #1a1814;
  --muted: #626262;
  --muted2: #9a958e;
  --line: #ddd9d0;
  --line-strong: #a7a7a7;
  --known: #16a34a;
  --known-bg: #dcfce7;
  --flag: #dc2626;
  --flag-bg: #fee2e2;
  --accent: #1e3a5f;
  --shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
}
html { scroll-behavior: smooth; }
body {
  font-family: "Skolar Sans PE", "Avenir Next", "Hiragino Sans", "Yu Gothic", sans-serif;
  background: var(--paper); color: var(--ink); line-height: 1.5;
  font-size: 15px;
}
.jp { font-family: "Iowan Old Style", "Hiragino Mincho ProN", "Yu Mincho", serif; }
ruby { ruby-position: over; ruby-align: center; }
rt   { font-size: 0.46em; line-height: 1; color: var(--muted2); }

header.hero {
  background: var(--accent); color: #fff;
  padding: 1.6rem 1.5rem 1.3rem;
  position: relative; overflow: hidden;
}
header.hero::before {
  content: '語彙'; font-family: "Hiragino Mincho ProN", serif;
  font-size: 8rem; font-weight: 600;
  position: absolute; right: -0.5rem; top: -1.5rem;
  opacity: 0.08; line-height: 1; pointer-events: none;
}
header.hero .eyebrow {
  font-size: 0.78rem; letter-spacing: 0.1em; opacity: 0.7;
  text-transform: uppercase; margin-bottom: 0.3rem;
}
header.hero h1 {
  font-family: "Iowan Old Style", "Hiragino Mincho ProN", "Yu Mincho", serif;
  font-size: 1.8rem; font-weight: 600;
}
header.hero .meta { display: flex; gap: 1rem; margin-top: 0.6rem; font-size: 0.85rem; opacity: 0.85; }
header.hero a.back {
  display: inline-block; color: #cfe2ff; text-decoration: none;
  font-size: 0.85rem; margin-bottom: 0.4rem;
}
header.hero a.back:hover { text-decoration: underline; }

.controls {
  position: sticky; top: 0; z-index: 10;
  background: var(--paper);
  border-bottom: 1px solid var(--line);
  padding: 0.7rem 1.2rem;
  display: flex; gap: 0.6rem; align-items: center; flex-wrap: wrap;
}
.controls input[type="search"] {
  flex: 1; min-width: 180px; max-width: 320px;
  padding: 0.45rem 0.7rem;
  border: 1px solid var(--line); border-radius: 6px;
  background: #fff; font-size: 0.9rem; color: var(--ink);
  outline: none;
}
.controls input[type="search"]:focus { border-color: var(--accent); }
.controls .pill-group { display: flex; gap: 0.3rem; flex-wrap: wrap; }
.controls .pill {
  padding: 0.32rem 0.7rem; border: 1px solid var(--line); border-radius: 999px;
  background: #fff; font-size: 0.82rem; color: var(--muted);
  cursor: pointer; user-select: none;
}
.controls .pill:hover { color: var(--ink); border-color: var(--muted2); }
.controls .pill.active {
  background: var(--accent); color: #fff; border-color: var(--accent);
}
.controls .pill.known.active   { background: var(--known); border-color: var(--known); }
.controls .pill.flagged.active { background: var(--flag);  border-color: var(--flag);  }
.controls .counter { margin-left: auto; font-size: 0.85rem; color: var(--muted); }
.controls .reset {
  font-size: 0.82rem; color: var(--muted); background: none; border: none;
  cursor: pointer; text-decoration: underline;
}

.status-banner {
  background: #fff3cd; border-bottom: 1px solid #f0d97a;
  color: #6b5208; padding: 0.5rem 1.2rem; font-size: 0.85rem;
  display: none;
}
.status-banner.show { display: block; }

main { padding: 1.2rem 1.2rem 3rem; }
.grid {
  display: grid; gap: 14px;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
}

.card {
  background: #fff;
  border: 1px solid var(--line);
  border-left: 4px solid var(--line);
  border-radius: 8px;
  padding: 12px 14px;
  box-shadow: var(--shadow);
  display: flex; flex-direction: column; gap: 8px;
  position: relative;
}
.card.known   { border-left-color: var(--known); background: color-mix(in srgb, var(--known-bg) 35%, #fff); }
.card.flagged { border-left-color: var(--flag);  background: color-mix(in srgb, var(--flag-bg)  35%, #fff); }
.card.known.flagged { border-left-color: var(--flag); }
.card.hide { display: none; }

.card-top {
  display: flex; justify-content: flex-end; align-items: flex-start;
  gap: 8px;
}
.card-actions { display: flex; gap: 4px; }
.icon-btn {
  width: 30px; height: 30px;
  display: inline-flex; align-items: center; justify-content: center;
  background: transparent; border: 1px solid var(--line); border-radius: 6px;
  font-size: 14px; cursor: pointer; color: var(--muted2);
  transition: all 0.12s;
}
.icon-btn:hover { color: var(--ink); border-color: var(--muted2); }
.icon-btn.known.on   { background: var(--known); border-color: var(--known); color: #fff; }
.icon-btn.flagged.on { background: var(--flag);  border-color: var(--flag);  color: #fff; }

.card-kanji {
  font-family: "Iowan Old Style", "Hiragino Mincho ProN", "Yu Mincho", serif;
  font-size: 1.5rem; line-height: 1.15; font-weight: 600;
}
.card-meaning { font-size: 0.85rem; color: var(--muted); }
.card-meaning .en { color: var(--ink); font-weight: 500; }
.card-meaning .zh { color: var(--muted2); }
.card-sentence {
  font-family: "Iowan Old Style", "Hiragino Mincho ProN", "Yu Mincho", serif;
  font-size: 1rem; padding: 6px 0; color: var(--ink);
  border-top: 1px dashed var(--line);
}
.card-sentence-translation {
  margin-top: -4px;
  color: var(--muted);
  font-size: 0.78rem;
  line-height: 1.35;
}
.card-sentence-translation .en { color: var(--ink); font-weight: 500; }
.card-sentence-translation .zh { color: var(--muted2); }
.card-bottom {
  display: flex; gap: 6px; align-items: center; flex-wrap: wrap;
  margin-top: auto;
}
.play-btn {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 9px;
  background: var(--paper2); border: 1px solid var(--line);
  border-radius: 6px; font-size: 0.78rem; color: var(--ink);
  cursor: pointer; font-weight: 500;
}
.play-btn:hover { background: #fff; border-color: var(--muted2); }
.play-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.play-btn.playing { background: var(--accent); color: #fff; border-color: var(--accent); }
.play-btn .triangle { font-size: 0.7rem; }
.details-link {
  margin-left: auto; font-size: 0.78rem; color: var(--muted);
  text-decoration: none;
}
.details-link:hover { color: var(--accent); text-decoration: underline; }
.card-index {
  color: var(--muted2);
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  padding-left: 4px;
}

/* ── Modal ── */
.modal-backdrop {
  position: fixed; inset: 0; background: rgba(15,17,22,0.55);
  backdrop-filter: blur(2px);
  display: none; align-items: flex-start; justify-content: center;
  padding: 4vh 1.5rem; z-index: 100;
  animation: mb-fade 0.15s ease;
}
.modal-backdrop.open { display: flex; }
@keyframes mb-fade { from { opacity: 0; } to { opacity: 1; } }
@keyframes mb-slide { from { transform: translateY(12px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
.modal {
  background: var(--paper); border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.25), 0 6px 18px rgba(0,0,0,0.12);
  max-width: 640px; width: 100%; max-height: 92vh; overflow: auto;
  position: relative; animation: mb-slide 0.18s ease;
}
.modal-head {
  position: sticky; top: 0; background: var(--paper); z-index: 2;
  padding: 18px 22px 12px; border-bottom: 1px solid var(--line);
  display: flex; gap: 12px; align-items: flex-start;
}
.modal-head .meta {
  font-size: 0.72rem; letter-spacing: 0.08em; color: var(--muted2);
  text-transform: uppercase; font-weight: 600; margin-bottom: 4px;
}
.modal-head .kanji {
  font-family: "Iowan Old Style", "Hiragino Mincho ProN", "Yu Mincho", serif;
  font-size: 2.1rem; font-weight: 600; line-height: 1.15;
}
.modal-head .verb { font-size: 0.85rem; color: var(--muted); margin-top: 4px; }
.modal-close {
  margin-left: auto; flex-shrink: 0;
  width: 32px; height: 32px; border: 1px solid var(--line); border-radius: 8px;
  background: #fff; cursor: pointer; font-size: 18px; color: var(--muted);
  display: flex; align-items: center; justify-content: center;
}
.modal-close:hover { color: var(--ink); border-color: var(--muted2); }
.modal-body { padding: 16px 22px 24px; display: flex; flex-direction: column; gap: 14px; }
.modal-actions { display: flex; gap: 8px; flex-wrap: wrap; padding-top: 4px; }
.modal-actions .icon-btn { width: auto; padding: 0 10px; height: 32px; gap: 6px; font-size: 0.85rem; }
.modal-actions .icon-btn.known.on   { background: var(--known); border-color: var(--known); color: #fff; }
.modal-actions .icon-btn.flagged.on { background: var(--flag);  border-color: var(--flag);  color: #fff; }
.modal-actions .play-btn { height: 32px; padding: 0 12px; font-size: 0.85rem; }
.modal-meaning { font-size: 0.95rem; }
.modal-meaning .en { font-weight: 600; }
.modal-meaning .zh { color: var(--muted); margin-top: 2px; }
.section-label {
  font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase;
  font-weight: 700; color: var(--muted2); margin-bottom: 6px;
}
.sentences { display: flex; flex-direction: column; gap: 6px; }
.sentence-row {
  font-family: "Iowan Old Style", "Hiragino Mincho ProN", "Yu Mincho", serif;
  font-size: 1.02rem; padding: 8px 12px;
  background: #fff; border: 1px solid var(--line); border-radius: 6px;
  display: flex; flex-direction: column; align-items: flex-start; gap: 4px;
}
.sentence-row.main { background: color-mix(in srgb, var(--accent) 5%, #fff); border-color: color-mix(in srgb, var(--accent) 25%, var(--line)); }
.sentence-row .badge { font-size: 0.65rem; letter-spacing: 0.06em; color: var(--accent); font-weight: 700; text-transform: uppercase; }
.sentence-row .sentence-translation { color: var(--muted); font-size: 0.86rem; line-height: 1.4; }
.sentence-row .sentence-translation .en { color: var(--ink); font-weight: 500; }
.sentence-row .sentence-translation .zh { color: var(--muted); }
.explanation {
  background: color-mix(in srgb, var(--muted) 6%, var(--paper));
  border-radius: 8px; padding: 12px 14px; font-size: 0.88rem;
  line-height: 1.65; color: var(--muted);
}
.explanation strong { color: var(--ink); }
.explanation ul { padding-left: 1.3em; margin: 0.3em 0; }
.explanation li { margin-top: 0.25em; }
.explanation hr { border: none; border-top: 1px solid var(--line); margin: 0.6em 0; }
.jlpt-tag {
  display: inline-block; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.04em;
  color: var(--muted); background: color-mix(in srgb, var(--muted) 14%, var(--paper));
  border-radius: 3px; padding: 1px 5px; margin-left: 2px;
}
.modal-foot {
  border-top: 1px solid var(--line); padding-top: 10px;
  display: flex; gap: 10px; align-items: center; justify-content: flex-end;
  font-size: 0.8rem;
}
.modal-foot a { color: var(--muted); text-decoration: none; }
.modal-foot a:hover { color: var(--accent); text-decoration: underline; }

@media (max-width: 540px) {
  .grid { grid-template-columns: 1fr; }
  header.hero { padding: 1.2rem 1rem 1rem; }
  header.hero h1 { font-size: 1.5rem; }
  main { padding: 1rem 0.8rem 2rem; }
  .modal-head .kanji { font-size: 1.7rem; }
  .modal-body { padding: 14px 16px 20px; }
}
"""


JS = r"""
const MARKS_URL = "%MARKS_URL%";
const LS_KEY = "n2_word_marks_v1";
const LS_FILTERS_KEY = "n2_word_filters_v1";

let marks = {};
let serverOk = false;
let currentAudio = null;
let entryData = {};
let unitNum = 0;
let lastFocused = null;

function loadLocal() {
  try { return JSON.parse(localStorage.getItem(LS_KEY) || "{}"); } catch { return {}; }
}
function saveLocal() {
  localStorage.setItem(LS_KEY, JSON.stringify(marks));
}
function setBanner(msg) {
  const b = document.getElementById("status-banner");
  if (!b) return;
  if (msg) { b.textContent = msg; b.classList.add("show"); }
  else     { b.classList.remove("show"); }
}

async function fetchServerMarks() {
  try {
    const r = await fetch(MARKS_URL + "/marks", { cache: "no-store" });
    if (!r.ok) throw new Error("status " + r.status);
    const data = await r.json();
    serverOk = true;
    return data.marks || {};
  } catch (e) {
    serverOk = false;
    setBanner("Offline — marks saved to browser only. Start marks_server.py to persist to disk.");
    return null;
  }
}

async function pushMark(id, entry) {
  if (!serverOk) { saveLocal(); return; }
  try {
    const r = await fetch(MARKS_URL + "/marks/" + id, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ known: !!entry.known, flagged: !!entry.flagged }),
    });
    if (!r.ok) throw new Error("status " + r.status);
    saveLocal();  // keep mirror up to date
  } catch (e) {
    serverOk = false;
    setBanner("Server connection lost — saving to browser only.");
    saveLocal();
  }
}

function applyMarkToCard(card) {
  const id = card.dataset.id;
  const m = marks[id] || {};
  card.classList.toggle("known",   !!m.known);
  card.classList.toggle("flagged", !!m.flagged);
  card.querySelector(".icon-btn.known").classList.toggle("on",   !!m.known);
  card.querySelector(".icon-btn.flagged").classList.toggle("on", !!m.flagged);
}

function toggleMark(card, key) {
  const id = card.dataset.id;
  const cur = marks[id] || { known: false, flagged: false };
  cur[key] = !cur[key];
  cur.updated_at = new Date().toISOString();
  if (!cur.known && !cur.flagged) {
    delete marks[id];
  } else {
    marks[id] = cur;
  }
  applyMarkToCard(card);
  pushMark(id, cur);
  applyFilters();
}

function playClip(btn) {
  const src = btn.dataset.src;
  if (!src) return;
  if (currentAudio) {
    currentAudio.pause();
    if (currentAudio._btn) currentAudio._btn.classList.remove("playing");
  }
  const audio = new Audio(src);
  audio._btn = btn;
  btn.classList.add("playing");
  audio.addEventListener("ended", () => btn.classList.remove("playing"));
  audio.addEventListener("error", () => {
    btn.classList.remove("playing");
    btn.title = "Audio not found: " + src;
  });
  audio.play().catch(() => btn.classList.remove("playing"));
  currentAudio = audio;
}

/* ── Modal ───────────────────────────────────────────── */
function rubyOrPlain(kanji, reading) {
  if (!reading || reading === kanji) return escapeHTML(kanji);
  return `<ruby><rb>${escapeHTML(kanji)}</rb><rt>${escapeHTML(reading)}</rt></ruby>`;
}
function escapeHTML(s) {
  return String(s || "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}
function sentenceRow(item, isMain=false) {
  const text = item && item.text ? item.text : "";
  const en = item && item.translation_en ? item.translation_en : "";
  const zh = item && item.translation_zh ? item.translation_zh : "";
  let trans = "";
  if (en || zh) {
    const parts = [];
    if (en) parts.push(`<span class="en">${escapeHTML(en)}</span>`);
    if (zh) parts.push(`<span class="zh">${escapeHTML(zh)}</span>`);
    trans = `<span class="sentence-translation">${parts.join(" / ")}</span>`;
  }
  const badge = isMain ? '<span class="badge">main</span>' : "";
  const cls = isMain ? "sentence-row main" : "sentence-row";
  return `<div class="${cls}">${badge}<span>${escapeHTML(text)}</span>${trans}</div>`;
}

function openDetail(id) {
  const e = entryData[id];
  if (!e) return;
  lastFocused = document.activeElement;
  const pad = String(id).padStart(3, "0");
  const unitPad = String(unitNum).padStart(2, "0");
  document.getElementById("modal-meta").textContent = `#${pad} · Unit ${unitPad}`;
  document.getElementById("modal-title").innerHTML = rubyOrPlain(e.kanji, e.reading);

  let mh = "";
  if (e.meaning_en) mh += `<div class="en">${escapeHTML(e.meaning_en)}</div>`;
  if (e.meaning_zh) mh += `<div class="zh">${escapeHTML(e.meaning_zh)}</div>`;
  document.getElementById("modal-meaning").innerHTML = mh;

  let rows = "";
  if (e.example_items && e.example_items.length) {
    for (const item of e.example_items) {
      rows += sentenceRow(item, item.position === 0);
    }
  } else {
    if (e.sentence) {
      rows += sentenceRow({text: e.sentence, translation_en: e.sentence_translation_en, translation_zh: e.sentence_translation_zh}, true);
    }
    for (const ex of (e.examples || [])) {
      rows += sentenceRow({text: ex}, false);
    }
  }
  document.getElementById("modal-sentences").innerHTML = rows;

  const expWrap = document.getElementById("modal-explanation-wrap");
  if (e.explanation_html) {
    document.getElementById("modal-explanation").innerHTML = e.explanation_html;
    expWrap.style.display = "";
  } else {
    expWrap.style.display = "none";
  }

  // Mirror known/flagged into the modal action buttons + wire them to the same card.
  const m = marks[id] || {};
  const knownBtn = document.querySelector(".modal-actions .icon-btn.known");
  const flagBtn  = document.querySelector(".modal-actions .icon-btn.flagged");
  knownBtn.classList.toggle("on", !!m.known);
  flagBtn.classList.toggle("on",  !!m.flagged);
  knownBtn.onclick = () => {
    toggleMark(document.querySelector(`.card[data-id="${id}"]`), "known");
    const cur = marks[id] || {};
    knownBtn.classList.toggle("on", !!cur.known);
  };
  flagBtn.onclick = () => {
    toggleMark(document.querySelector(`.card[data-id="${id}"]`), "flagged");
    const cur = marks[id] || {};
    flagBtn.classList.toggle("on", !!cur.flagged);
  };

  // Audio buttons in the modal
  const card = document.querySelector(`.card[data-id="${id}"]`);
  const cardPlays = card ? card.querySelectorAll(".play-btn") : [];
  const modalPlays = document.querySelectorAll(".modal-actions .play-btn");
  modalPlays.forEach((btn, i) => {
    const src = cardPlays[i] ? cardPlays[i].dataset.src : "";
    btn.dataset.src = src || "";
    btn.disabled = !src;
    btn.onclick = () => playClip(btn);
  });

  // Footer link to long-form page
  const longLink = document.getElementById("modal-long-link");
  if (longLink) longLink.href = `../by_unit/unit_${unitPad}.html#w${id}`;

  document.getElementById("backdrop").classList.add("open");
  document.querySelector(".modal-close").focus();
}

function closeDetail() {
  document.getElementById("backdrop").classList.remove("open");
  if (currentAudio) { currentAudio.pause(); if (currentAudio._btn) currentAudio._btn.classList.remove("playing"); }
  if (lastFocused) lastFocused.focus();
}

/* ── Filters (persisted) ─────────────────────────────── */
const filters = { search: "", state: "all" };

function loadFilters() {
  try {
    const raw = localStorage.getItem(LS_FILTERS_KEY);
    if (!raw) return;
    const o = JSON.parse(raw);
    if (typeof o.search === "string") filters.search = o.search;
    if (typeof o.state === "string")  filters.state  = o.state;
  } catch {}
}
function saveFilters() {
  localStorage.setItem(LS_FILTERS_KEY, JSON.stringify(filters));
}

function applyFilters() {
  const q = filters.search.trim().toLowerCase();
  let shown = 0;
  const cards = document.querySelectorAll(".card");
  cards.forEach(card => {
    const m = marks[card.dataset.id] || {};
    let stateOk = true;
    if (filters.state === "unmarked") stateOk = !m.known && !m.flagged;
    else if (filters.state === "known")   stateOk = !!m.known;
    else if (filters.state === "flagged") stateOk = !!m.flagged;

    let searchOk = true;
    if (q) {
      const hay = card.dataset.search || "";
      searchOk = hay.includes(q);
    }
    const visible = stateOk && searchOk;
    card.classList.toggle("hide", !visible);
    if (visible) shown++;
  });
  const counter = document.getElementById("counter");
  if (counter) counter.textContent = `showing ${shown} / ${cards.length}`;
}

function syncControlsToFilters() {
  const search = document.getElementById("search");
  if (search) search.value = filters.search;
  document.querySelectorAll(".state-pill").forEach(p => {
    p.classList.toggle("active", p.dataset.state === filters.state);
  });
}

function wireControls() {
  document.getElementById("search").addEventListener("input", e => {
    filters.search = e.target.value.toLowerCase();
    saveFilters();
    applyFilters();
  });
  document.querySelectorAll(".state-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".state-pill").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      filters.state = pill.dataset.state;
      saveFilters();
      applyFilters();
    });
  });
  const reset = document.getElementById("reset-filters");
  if (reset) reset.addEventListener("click", () => {
    filters.search = ""; filters.state = "all";
    saveFilters();
    syncControlsToFilters();
    applyFilters();
  });
}

function wireCards() {
  document.querySelectorAll(".card").forEach(card => {
    card.querySelector(".icon-btn.known")
        .addEventListener("click", e => { e.stopPropagation(); toggleMark(card, "known"); });
    card.querySelector(".icon-btn.flagged")
        .addEventListener("click", e => { e.stopPropagation(); toggleMark(card, "flagged"); });
    card.querySelectorAll(".play-btn").forEach(btn => {
      btn.addEventListener("click", e => { e.stopPropagation(); playClip(btn); });
    });
    const details = card.querySelector(".details-link");
    if (details) details.addEventListener("click", e => {
      e.stopPropagation();
      openDetail(card.dataset.id);
    });
  });
}

function wireModal() {
  const backdrop = document.getElementById("backdrop");
  backdrop.addEventListener("click", e => {
    if (e.target === backdrop) closeDetail();
  });
  document.querySelector(".modal-close").addEventListener("click", closeDetail);
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && backdrop.classList.contains("open")) closeDetail();
  });
}

async function init() {
  const entryEl = document.getElementById("entry-data");
  if (entryEl) entryData = JSON.parse(entryEl.textContent);
  const meta = document.querySelector("meta[name=unit]");
  if (meta) unitNum = parseInt(meta.content, 10) || 0;

  loadFilters();
  const local = loadLocal();
  const server = await fetchServerMarks();
  if (server !== null) {
    marks = server;
    saveLocal();
  } else {
    marks = local;
  }
  document.querySelectorAll(".card").forEach(applyMarkToCard);
  wireControls();
  wireCards();
  wireModal();
  syncControlsToFilters();
  applyFilters();
}

document.addEventListener("DOMContentLoaded", init);
"""


def headword_html(kanji: str, reading: str) -> str:
    k = html.escape(kanji)
    r = html.escape(reading)
    if not reading or kanji == reading:
        return k
    return f"<ruby><rb>{k}</rb><rt>{r}</rt></ruby>"


def clip_url(clip_path: str) -> str:
    if not clip_path:
        return ""
    p = clip_path.replace("\\", "/")
    p = re.sub(r"^output/", "", p)
    return CLIP_PREFIX_FROM_CARDS + p


def search_blob(entry: dict) -> str:
    parts = [
        entry.get("kanji") or "",
        entry.get("headword_text") or "",
        entry.get("reading") or "",
        entry.get("meaning_en") or "",
        entry.get("meaning_zh") or "",
        entry.get("sentence") or "",
        entry.get("sentence_translation_en") or "",
        entry.get("sentence_translation_zh") or "",
    ]
    return " ".join(parts).lower()


def render_card(e: dict, unit_num: int) -> str:
    idx = e["index"]
    kanji = e.get("headword_text") or e.get("kanji", "")
    reading = e.get("reading", "")
    meaning_en = e.get("meaning_en", "")
    meaning_zh = e.get("meaning_zh", "")
    sentence = e.get("sentence", "")
    sentence_translation_en = e.get("sentence_translation_en", "")
    sentence_translation_zh = e.get("sentence_translation_zh", "")
    word_clip = clip_url(e.get("word_clip") or "")
    sent_clip = clip_url(e.get("sentence_clip") or "")
    search = html.escape(search_blob(e), quote=True)

    meaning_parts = []
    if meaning_en:
        meaning_parts.append(f'<span class="en">{html.escape(meaning_en)}</span>')
    if meaning_zh:
        meaning_parts.append(f'<span class="zh">{html.escape(meaning_zh)}</span>')
    meaning_html = (
        f'<div class="card-meaning">{" · ".join(meaning_parts)}</div>'
        if meaning_parts else ""
    )

    sentence_html = (
        f'<div class="card-sentence">{html.escape(sentence)}</div>'
        if sentence else ""
    )
    sentence_translation_parts = []
    if sentence_translation_en:
        sentence_translation_parts.append(f'<span class="en">{html.escape(sentence_translation_en)}</span>')
    if sentence_translation_zh:
        sentence_translation_parts.append(f'<span class="zh">{html.escape(sentence_translation_zh)}</span>')
    sentence_translation_html = (
        f'<div class="card-sentence-translation">{" / ".join(sentence_translation_parts)}</div>'
        if sentence_translation_parts else ""
    )

    word_btn = (
        f'<button class="play-btn" data-src="{html.escape(word_clip, quote=True)}" title="Play word">'
        f'<span class="triangle">▶</span> word</button>'
        if word_clip else
        '<button class="play-btn" disabled>▶ word</button>'
    )
    sent_btn = (
        f'<button class="play-btn" data-src="{html.escape(sent_clip, quote=True)}" title="Play sentence">'
        f'<span class="triangle">▶</span> sentence</button>'
        if sent_clip else
        '<button class="play-btn" disabled>▶ sentence</button>'
    )

    return (
        f'<article class="card" data-id="{idx}" data-unit="{unit_num}" data-search="{search}">'
        f'  <div class="card-top">'
        f'    <span class="card-actions">'
        f'      <button class="icon-btn known"   title="Mark as known">✓</button>'
        f'      <button class="icon-btn flagged" title="Flag for review">⚑</button>'
        f'    </span>'
        f'  </div>'
        f'  <div class="card-kanji">{headword_html(kanji, reading)}</div>'
        f'  {meaning_html}'
        f'  {sentence_html}'
        f'  {sentence_translation_html}'
        f'  <div class="card-bottom">'
        f'    {word_btn}'
        f'    {sent_btn}'
        f'    <button class="details-link" type="button">details →</button>'
        f'    <span class="card-index">#{idx:03d}</span>'
        f'  </div>'
        f'</article>'
    )


def page_shell(title: str, body: str, unit_num: int | None = None) -> str:
    js = JS.replace("%MARKS_URL%", MARKS_SERVER_URL)
    unit_meta = (
        f'<meta name="unit" content="{unit_num}" />\n' if unit_num is not None else ""
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="ja">\n<head>\n'
        '<meta charset="utf-8" />\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        + unit_meta +
        f"<title>{html.escape(title)}</title>\n"
        f"<style>{CSS}</style>\n"
        "</head>\n<body>\n"
        f"{body}\n"
        f"<script>{js}</script>\n"
        "</body>\n</html>\n"
    )


MODAL_HTML = """
<div class="modal-backdrop" id="backdrop" aria-hidden="true">
  <div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
    <div class="modal-head">
      <div>
        <div class="meta" id="modal-meta"></div>
        <div class="kanji" id="modal-title"></div>
      </div>
      <button type="button" class="modal-close" aria-label="Close">×</button>
    </div>
    <div class="modal-body">
      <div class="modal-actions">
        <button type="button" class="icon-btn known">✓ Known</button>
        <button type="button" class="icon-btn flagged">⚑ Flag</button>
        <button type="button" class="play-btn">▶ word</button>
        <button type="button" class="play-btn">▶ sentence</button>
      </div>
      <div class="modal-meaning" id="modal-meaning"></div>
      <div>
        <div class="section-label">Sentences</div>
        <div class="sentences" id="modal-sentences"></div>
      </div>
      <div id="modal-explanation-wrap">
        <div class="section-label">Explanation</div>
        <div class="explanation" id="modal-explanation"></div>
      </div>
      <div class="modal-foot">
        <a id="modal-long-link" target="_blank" rel="noopener">Open full page →</a>
      </div>
    </div>
  </div>
</div>
"""


def entry_detail_payload(e: dict) -> dict:
    """Slice of `e` that the modal needs (no audio paths — modal reuses card's)."""
    return {
        "kanji": e.get("headword_text") or e.get("kanji", ""),
        "reading": e.get("reading", "") or "",
        "meaning_en": e.get("meaning_en", "") or "",
        "meaning_zh": e.get("meaning_zh", "") or "",
        "sentence": e.get("sentence", "") or "",
        "sentence_translation_en": e.get("sentence_translation_en", "") or "",
        "sentence_translation_zh": e.get("sentence_translation_zh", "") or "",
        "examples": list(e.get("examples") or []),
        "example_items": list(e.get("example_items") or []),
        "explanation_html": _md_explanation_html(e.get("explanation", "") or ""),
    }


def render_unit_page(unit_num: int, unit_title: str, entries: list) -> str:
    cards = "\n".join(render_card(e, unit_num) for e in entries)
    num_str = f"{unit_num:02d}"
    payload = {str(e["index"]): entry_detail_payload(e) for e in entries}
    # Embedded JSON: keep "</" from prematurely closing the script tag.
    payload_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    body = f"""
<header class="hero">
  <a class="back" href="index.html">← All units (cards)</a>
  <div class="eyebrow">Unit {num_str} · Card view</div>
  <h1>{html.escape(unit_title)}</h1>
  <div class="meta"><span>{len(entries)} words</span><span><a href="../by_unit/unit_{num_str}.html" style="color:#cfe2ff">full detail page →</a></span></div>
</header>
<div class="controls">
  <input id="search" type="search" placeholder="Search kanji, reading, meaning, sentence…" />
  <div class="pill-group">
    <button class="pill state-pill active" data-state="all">All</button>
    <button class="pill state-pill"        data-state="unmarked">Unmarked</button>
    <button class="pill state-pill known"   data-state="known">✓ Known</button>
    <button class="pill state-pill flagged" data-state="flagged">⚑ Flagged</button>
  </div>
  <button class="reset" id="reset-filters">reset</button>
  <span class="counter" id="counter"></span>
</div>
<div class="status-banner" id="status-banner"></div>
<main><div class="grid">
{cards}
</div></main>
{MODAL_HTML}
<script type="application/json" id="entry-data">{payload_json}</script>
"""
    return page_shell(f"Unit {num_str} {unit_title} — Cards", body, unit_num=unit_num)


def render_index(unit_info: list) -> str:
    total = sum(c for _, _, c in unit_info)
    cards = []
    for num, title, count in unit_info:
        num_str = f"{num:02d}"
        cards.append(
            f'<a class="unit-link" href="unit_{num_str}.html">'
            f'<span class="n">Unit {num_str}</span>'
            f'<span class="t jp">{html.escape(title)}</span>'
            f'<span class="c">{count} words</span>'
            f'</a>'
        )
    body = f"""
<header class="hero">
  <a class="back" href="../index.html">← Words index</a>
  <div class="eyebrow">Card view · All units</div>
  <h1>N2 語彙 — Card view</h1>
  <div class="meta"><span>{len(unit_info)} units</span><span>{total} words</span></div>
</header>
<main>
  <p style="color:var(--muted); font-size:0.88rem; margin-bottom:1rem;">
    Compact grid with known/flagged marks. Run <code>python marks_server.py</code>
    in the project root to persist marks to <code>output/n2vocab.sqlite</code>;
    otherwise marks are saved in this browser only.
  </p>
  <div class="grid index-grid">
  {"".join(cards)}
  </div>
</main>
<style>
  .index-grid {{ grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }}
  .unit-link {{
    display: flex; flex-direction: column; gap: 4px;
    padding: 14px 16px;
    background: #fff; border: 1px solid var(--line); border-radius: 8px;
    text-decoration: none; color: inherit;
    box-shadow: var(--shadow);
  }}
  .unit-link:hover {{ border-color: var(--accent); }}
  .unit-link .n {{ font-size: 0.72rem; letter-spacing: 0.08em; color: var(--muted2); text-transform: uppercase; font-weight: 600; }}
  .unit-link .t {{ font-size: 1.05rem; font-weight: 600; }}
  .unit-link .c {{ font-size: 0.8rem; color: var(--muted); }}
</style>
"""
    return page_shell("N2 語彙 — Card view", body)


def main():
    if not DB_PATH.exists():
        print(
            f"ERROR: {DB_PATH} not found. Run `python db/import_vocabulary.py` first.",
            file=sys.stderr,
        )
        sys.exit(1)
    data = load_entries(book_code="N2")

    by_unit: dict[int, list] = defaultdict(list)
    for e in data:
        by_unit[e["unit"]["number"]].append(e)

    unit_meta: OrderedDict[int, tuple] = OrderedDict()
    for unit_num in sorted(by_unit):
        entries = by_unit[unit_num]
        first_header = entries[0]["unit"]["header"]
        short_title = re.sub(r"^Unit\s+\d+\s+", "", first_header).strip()
        short_title = re.sub(r"\s*&\s*Column.*$", "", short_title).strip()
        unit_meta[unit_num] = (short_title, len(entries))

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    unit_info = [(num, title, count) for num, (title, count) in unit_meta.items()]
    (OUT_DIR / "index.html").write_text(render_index(unit_info), encoding="utf-8")
    print(f"  wrote {OUT_DIR / 'index.html'}")

    for unit_num, entries in sorted(by_unit.items()):
        short_title, _ = unit_meta[unit_num]
        out = OUT_DIR / f"unit_{unit_num:02d}.html"
        out.write_text(render_unit_page(unit_num, short_title, entries), encoding="utf-8")
        print(f"  wrote {out}  ({len(entries)} cards)")

    print(f"\nDone. {1 + len(by_unit)} files in {OUT_DIR}/")


if __name__ == "__main__":
    main()
