import { useEffect, useMemo, useRef, useState } from "react";

import { getEntries, getUnits } from "./api";
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
      <div className="react-layout">
        <section className="react-list" aria-label="Vocabulary playback list">
          {entries.map((entry, index) => <button key={entry.entry_id} ref={index === activeIndex ? activeRef : null} className={index === activeIndex ? "is-active" : ""} onClick={() => { setActiveIndex(index); setActivePhase("word"); }}><span>{entry.kanji}</span><small>{entry.reading}</small></button>)}
        </section>
        <section className="react-current" aria-label="Current vocabulary item">
          {activeEntry ? <><span className="eyebrow">{activeEntry.book_code} #{String(activeEntry.source_index).padStart(3, "0")}</span><h2>{activeEntry.kanji}</h2><ruby>{activeEntry.kanji}<rt>{activeEntry.reading}</rt></ruby><p>{activeEntry.meaning_en || activeEntry.meaning_zh}</p><button type="button" onClick={() => setActivePhase("word")} className={activePhase === "word" ? "phase-active" : ""}>Word</button><button type="button" onClick={() => setActivePhase("sentence")} className={activePhase === "sentence" ? "phase-active" : ""} disabled={!activeEntry.sentence_audio_url}>Sentence</button></> : <p>Loading vocabulary…</p>}
          <nav className="react-nav"><button type="button" onClick={() => move(-1)} disabled={activeIndex === 0}>Previous</button><button type="button" onClick={() => move(1)} disabled={!entries.length || activeIndex === entries.length - 1}>Next</button></nav>
        </section>
      </div>
      <RailPlayer target={target} onEnded={() => move(1)} />
    </main>
  );
}
