import { useEffect, useMemo, useRef, useState } from "react";

import { getEntries, getEntry, getUnits } from "./api";
import { RailPlayer } from "./features/player/RailPlayer";
import type { AudioTarget, Entry, UnitSummary } from "./types";

function targetFor(entry: Entry, phase: "word" | "sentence"): AudioTarget | null {
  const url = phase === "word" ? entry.word_audio_url : entry.sentence_audio_url;
  return url ? {entry, phase, url} : null;
}

export function App() {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [units, setUnits] = useState<UnitSummary[]>([]);
  const [unit, setUnit] = useState<number>();
  const [activeIndex, setActiveIndex] = useState(0);
  const [activePhase, setActivePhase] = useState<"word" | "sentence">("word");
  const [detail, setDetail] = useState<Entry>();
  const [listWidth, setListWidth] = useState(360);
  const [draggingDivider, setDraggingDivider] = useState(false);
  const activeRef = useRef<HTMLButtonElement | null>(null);
  const activeEntry = entries[activeIndex];
  const target = useMemo(() => activeEntry ? targetFor(activeEntry, activePhase) : null, [activeEntry, activePhase]);

  useEffect(() => {
    getUnits().then((payload) => setUnits(payload.items)).catch(console.error);
  }, []);

  useEffect(() => {
    getEntries("N2", unit).then((payload) => {
      setEntries(payload.items);
      setActiveIndex(0);
    }).catch(console.error);
  }, [unit]);

  useEffect(() => {
    activeRef.current?.scrollIntoView({behavior: "smooth", block: "center"});
  }, [activeIndex]);

  useEffect(() => {
    if (!activeEntry) return;
    getEntry(activeEntry.entry_id).then(setDetail).catch(console.error);
  }, [activeEntry]);

  useEffect(() => {
    if (!draggingDivider) return;
    const move = (event: PointerEvent) => setListWidth(Math.min(620, Math.max(220, event.clientX)));
    const stop = () => setDraggingDivider(false);
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop, {once: true});
    return () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", stop); };
  }, [draggingDivider]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLElement && event.target.closest("input, select, textarea")) return;
      if (event.code === "Space") { event.preventDefault(); document.querySelector<HTMLButtonElement>(".react-player-controls button")?.click(); }
      else if (event.key === "ArrowRight" || event.key.toLowerCase() === "d") move(1);
      else if (event.key === "ArrowLeft" || event.key.toLowerCase() === "a") move(-1);
      else if (event.key.toLowerCase() === "r") document.querySelector<HTMLButtonElement>(".react-player-controls button:nth-of-type(2)")?.click();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  function move(offset: number) {
    setActiveIndex((index) => Math.min(entries.length - 1, Math.max(0, index + offset)));
    setActivePhase("word");
  }

  return (
    <main className="react-shell">
      <header className="react-header">
        <div><span className="eyebrow">N2 VOCABULARY</span><h1>Study Wall · React preview</h1></div>
        <a href="/study-wall-rail.html">Back to current rail</a>
      </header>
      <div className="react-toolbar">
        <label>Section <select value={unit || ""} onChange={(event) => setUnit(event.target.value ? Number(event.target.value) : undefined)}><option value="">All sections</option>{units.map((item) => <option key={item.number} value={item.number}>{item.title || item.header}</option>)}</select></label>
        <span>{entries.length} words · React/Vite migration preview</span>
      </div>
      <div className="react-layout" style={{gridTemplateColumns: `${listWidth}px 12px minmax(0, 1fr)`}}>
        <section className="react-list" aria-label="Vocabulary playback list">
          {entries.map((entry, index) => <button key={entry.entry_id} ref={index === activeIndex ? activeRef : null} className={index === activeIndex ? "is-active" : ""} onClick={() => { setActiveIndex(index); setActivePhase("word"); }}><span>{entry.kanji}</span><small>{entry.reading}</small></button>)}
        </section>
        <button className="react-divider" type="button" aria-label="Adjust playback list width" onPointerDown={(event) => { event.currentTarget.setPointerCapture(event.pointerId); setDraggingDivider(true); }} />
        <section className="react-current" aria-label="Current vocabulary item">
          {activeEntry ? <><span className="eyebrow">{activeEntry.book_code} #{String(activeEntry.source_index).padStart(3, "0")}</span><h2>{activeEntry.kanji}</h2><ruby>{activeEntry.kanji}<rt>{activeEntry.reading}</rt></ruby><p>{activeEntry.meaning_en || activeEntry.meaning_zh}</p><div className="react-phase-buttons"><button type="button" onClick={() => setActivePhase("word")} className={activePhase === "word" ? "phase-active" : ""}>Word</button><button type="button" onClick={() => setActivePhase("sentence")} className={activePhase === "sentence" ? "phase-active" : ""} disabled={!activeEntry.sentence_audio_url}>Sentence</button></div>{detail?.sentence ? <div className="react-sentence"><strong>{detail.sentence}</strong><span>{detail.sentence_translation_en || detail.sentence_translation_zh}</span></div> : null}{detail?.explanation_md ? <details><summary>Sentence explanation</summary><p>{detail.explanation_md}</p></details> : null}</> : <p>Loading vocabulary…</p>}
          <nav className="react-nav"><button type="button" onClick={() => move(-1)} disabled={activeIndex === 0}>Previous</button><button type="button" onClick={() => move(1)} disabled={!entries.length || activeIndex === entries.length - 1}>Next</button></nav>
        </section>
      </div>
      <RailPlayer target={target} onEnded={() => move(1)} />
    </main>
  );
}
