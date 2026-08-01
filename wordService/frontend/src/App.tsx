import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import {
  exportUnitFlaggedAudio,
  getBooks,
  getEntries,
  getEntry,
  getStarredSentences,
  getSummary,
  getUnits,
  updateExampleStar,
  updateMark,
} from "./api";
import { MarkdownContent } from "./features/explanation/MarkdownContent";
import { RailPlayer } from "./features/player/RailPlayer";
import type {
  AudioTarget,
  BookSummary,
  Entry,
  StarredSentence,
  UnitSummary,
  VocabularySummary,
} from "./types";

type PlaybackPhase = "word" | "sentence";
type PlaybackMode = "words" | "sentences" | "both";
type FilterState = "all" | "unmarked" | "known" | "flagged";

const PLAYBACK_SETTINGS_KEY = "n2-word-service:react-playback-settings:v1";
const DEFAULT_SILENCE_MS = 500;

type StoredPlaybackSettings = {
  postWordSilenceMs?: number;
  postSentenceSilenceMs?: number;
  playbackMode?: PlaybackMode;
};

type PendingSilence = {
  remainingMs: number;
  startedAt: number | null;
  callback: () => void;
};

function targetFor(entry: Entry, phase: PlaybackPhase): AudioTarget | null {
  const url = phase === "word" ? entry.word_audio_url : entry.sentence_audio_url;
  return url ? {entry, phase, url} : null;
}

function unitLabel(unit?: UnitSummary | Entry["unit"]) {
  if (!unit) return "All sections";
  return `U${String(unit.number).padStart(2, "0")} ${unit.title || unit.header}`;
}

function normalizeSilence(value: unknown) {
  const silence = Number(value);
  return Number.isFinite(silence) ? Math.min(3000, Math.max(0, Math.round(silence / 100) * 100)) : DEFAULT_SILENCE_MS;
}

function readPlaybackSettings(): {postWordSilence: number; postSentenceSilence: number; mode: PlaybackMode} {
  try {
    const raw = window.localStorage.getItem(PLAYBACK_SETTINGS_KEY);
    const saved = raw ? JSON.parse(raw) as StoredPlaybackSettings : {};
    const mode = saved.playbackMode === "words" || saved.playbackMode === "sentences" || saved.playbackMode === "both"
      ? saved.playbackMode
      : "both";
    return {
      postWordSilence: normalizeSilence(saved.postWordSilenceMs),
      postSentenceSilence: normalizeSilence(saved.postSentenceSilenceMs),
      mode,
    };
  } catch {
    return {postWordSilence: DEFAULT_SILENCE_MS, postSentenceSilence: DEFAULT_SILENCE_MS, mode: "both"};
  }
}

function savePlaybackSettings(postWordSilence: number, postSentenceSilence: number, mode: PlaybackMode) {
  window.localStorage.setItem(PLAYBACK_SETTINGS_KEY, JSON.stringify({
    postWordSilenceMs: postWordSilence,
    postSentenceSilenceMs: postSentenceSilence,
    playbackMode: mode,
  }));
}

export function App() {
  const [books, setBooks] = useState<BookSummary[]>([]);
  const [selectedBook, setSelectedBook] = useState("N2");
  const [summary, setSummary] = useState<VocabularySummary>();
  const [units, setUnits] = useState<UnitSummary[]>([]);
  const [selectedUnit, setSelectedUnit] = useState<number | null>(null);
  const [filterState, setFilterState] = useState<FilterState>("all");
  const [search, setSearch] = useState("");
  const [entries, setEntries] = useState<Entry[]>([]);
  const [entriesLoading, setEntriesLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [activePhase, setActivePhase] = useState<PlaybackPhase>("word");
  const [detail, setDetail] = useState<Entry>();
  const [listWidth, setListWidth] = useState(320);
  const [draggingDivider, setDraggingDivider] = useState(false);
  const [coveredEntryIds, setCoveredEntryIds] = useState<Set<number>>(() => new Set());
  const [blurred, setBlurred] = useState(false);
  const [showStarred, setShowStarred] = useState(false);
  const [starredSentences, setStarredSentences] = useState<StarredSentence[]>([]);
  const [selectedStarredKey, setSelectedStarredKey] = useState<string>();
  const [status, setStatus] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const savedSettings = useMemo(readPlaybackSettings, []);
  const [postWordSilence, setPostWordSilence] = useState(savedSettings.postWordSilence);
  const [postSentenceSilence, setPostSentenceSilence] = useState(savedSettings.postSentenceSilence);
  const [playbackMode, setPlaybackMode] = useState<PlaybackMode>(savedSettings.mode);
  const [autoAdvance, setAutoAdvance] = useState(true);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playRequest, setPlayRequest] = useState(0);
  const [replayRequest, setReplayRequest] = useState(0);
  const [pauseRequest, setPauseRequest] = useState(0);
  const [stopRequest, setStopRequest] = useState(0);
  const [isSilencePlaying, setIsSilencePlaying] = useState(false);
  const [isSilencePaused, setIsSilencePaused] = useState(false);
  const activeRef = useRef<HTMLButtonElement | null>(null);
  const layoutRef = useRef<HTMLDivElement | null>(null);
  const currentRef = useRef<HTMLElement | null>(null);
  const endTimerRef = useRef<number | null>(null);
  const endGenerationRef = useRef(0);
  const pendingSilenceRef = useRef<PendingSilence | null>(null);
  const autoAdvanceRef = useRef(autoAdvance);
  const activeEntry = entries[activeIndex];
  const target = useMemo(
    () => (activeEntry ? targetFor(activeEntry, activePhase) : null),
    [activeEntry, activePhase],
  );
  const currentBook = books.find((book) => book.code === selectedBook);
  const selectedStarred = starredSentences.find((item) => (
    `${item.entry_id}:${item.position}` === selectedStarredKey
  ));
  const allVisibleCovered = entries.length > 0 && entries.every((entry) => coveredEntryIds.has(entry.entry_id));

  useEffect(() => {
    autoAdvanceRef.current = autoAdvance;
  }, [autoAdvance]);

  useEffect(() => {
    getBooks()
      .then((payload) => setBooks(payload.items))
      .catch((error: unknown) => setStatus(error instanceof Error ? error.message : "Could not load books."));
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getSummary(selectedBook), getUnits(selectedBook)])
      .then(([nextSummary, nextUnits]) => {
        if (cancelled) return;
        setSummary(nextSummary);
        setUnits(nextUnits.items);
      })
      .catch((error: unknown) => {
        if (!cancelled) setStatus(error instanceof Error ? error.message : "Could not load sections.");
      });
    return () => { cancelled = true; };
  }, [selectedBook]);

  useEffect(() => {
    let cancelled = false;
    setEntriesLoading(true);
    getEntries(selectedBook, selectedUnit ?? undefined, filterState, search)
      .then((payload) => {
        if (cancelled) return;
        setEntries(payload.items);
        setActiveIndex(0);
        setActivePhase(playbackMode === "sentences" && payload.items[0]?.sentence_audio_url ? "sentence" : "word");
      })
      .catch((error: unknown) => {
        if (!cancelled) setStatus(error instanceof Error ? error.message : "Could not load vocabulary.");
      })
      .finally(() => {
        if (!cancelled) setEntriesLoading(false);
      });
    return () => { cancelled = true; };
  }, [filterState, playbackMode, search, selectedBook, selectedUnit]);

  useEffect(() => {
    if (!activeEntry) {
      setDetail(undefined);
      return undefined;
    }
    let cancelled = false;
    getEntry(activeEntry.entry_id, selectedBook)
      .then((nextDetail) => { if (!cancelled) setDetail(nextDetail); })
      .catch((error: unknown) => { if (!cancelled) setStatus(error instanceof Error ? error.message : "Could not load word details."); });
    return () => { cancelled = true; };
  }, [activeEntry, selectedBook]);

  useEffect(() => {
    if (!showStarred) return undefined;
    let cancelled = false;
    getStarredSentences(selectedBook, selectedUnit ?? undefined)
      .then((payload) => {
        if (cancelled) return;
        setStarredSentences(payload.items);
        setSelectedStarredKey((current) => payload.items.some((item) => `${item.entry_id}:${item.position}` === current)
          ? current
          : payload.items[0] ? `${payload.items[0].entry_id}:${payload.items[0].position}` : undefined);
      })
      .catch((error: unknown) => { if (!cancelled) setStatus(error instanceof Error ? error.message : "Could not load starred sentences."); });
    return () => { cancelled = true; };
  }, [selectedBook, selectedUnit, showStarred]);

  useEffect(() => {
    activeRef.current?.scrollIntoView({behavior: "smooth", block: "center"});
  }, [activeIndex, entries]);

  useLayoutEffect(() => {
    const current = currentRef.current;
    if (!current) return;
    // A long explanation can leave the detail pane scrolled down. Reset it
    // before the newly focused word is painted so its heading cannot remain
    // hidden above the pane when playback advances.
    current.scrollTop = 0;
    current.scrollLeft = 0;
  }, [activeEntry?.entry_id, selectedBook, showStarred]);

  useEffect(() => {
    if (!draggingDivider) return undefined;
    const move = (event: PointerEvent) => {
      const left = layoutRef.current?.getBoundingClientRect().left || 0;
      setListWidth(Math.min(620, Math.max(220, Math.round(event.clientX - left))));
    };
    const stop = () => setDraggingDivider(false);
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop, {once: true});
    window.addEventListener("pointercancel", stop, {once: true});
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
    };
  }, [draggingDivider]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const targetElement = event.target;
      const isWaveformInput = targetElement instanceof HTMLElement && !!targetElement.closest(".line-waveform input");
      if (!isWaveformInput && targetElement instanceof HTMLElement && targetElement.closest("input, select, textarea, [contenteditable='true']")) return;
      if (event.repeat) return;
      const key = event.key.toLowerCase();
      if (event.code === "Space") {
        event.preventDefault();
        togglePlayback();
      } else if (event.key === "ArrowRight" || key === "d") {
        event.preventDefault();
        moveClip(1);
      } else if (event.key === "ArrowLeft" || key === "a") {
        event.preventDefault();
        moveClip(-1);
      } else if (key === "r") {
        event.preventDefault();
        replayFocused();
      } else if (key === "b") {
        event.preventDefault();
        setBlurred((current) => !current);
      } else if (key === "f") {
        event.preventDefault();
        void toggleMark("flagged");
      } else if (key === "k" || event.key === "Enter") {
        event.preventDefault();
        void toggleMark("known");
      } else if (event.key === "Escape" && settingsOpen) {
        setSettingsOpen(false);
      }
    };
    document.addEventListener("keydown", onKey, {capture: true});
    return () => document.removeEventListener("keydown", onKey, {capture: true});
  });

  useEffect(() => () => {
    if (endTimerRef.current !== null) window.clearTimeout(endTimerRef.current);
  }, []);

  const refreshCatalog = useCallback(async () => {
    const [nextSummary, nextUnits] = await Promise.all([getSummary(selectedBook), getUnits(selectedBook)]);
    setSummary(nextSummary);
    setUnits(nextUnits.items);
  }, [selectedBook]);

  const clearEndTimer = useCallback(() => {
    endGenerationRef.current += 1;
    if (endTimerRef.current !== null) {
      window.clearTimeout(endTimerRef.current);
      endTimerRef.current = null;
    }
  }, []);

  const cancelEndTimer = useCallback(() => {
    clearEndTimer();
    pendingSilenceRef.current = null;
    setIsSilencePlaying(false);
    setIsSilencePaused(false);
  }, [clearEndTimer]);

  const startPendingSilence = useCallback(() => {
    // The AudioBuffer source has already ended, but this configured boundary
    // gap is still part of the learner's playback run. Keeping it here lets
    // Space pause/resume the gap instead of treating the ended clip as new.
    const pending = pendingSilenceRef.current;
    if (!pending) return false;

    if (pending.remainingMs <= 0) {
      pendingSilenceRef.current = null;
      setIsSilencePlaying(false);
      setIsSilencePaused(false);
      if (autoAdvanceRef.current) pending.callback();
      return true;
    }

    pending.startedAt = performance.now();
    setIsSilencePlaying(true);
    setIsSilencePaused(false);
    const generation = endGenerationRef.current;
    endTimerRef.current = window.setTimeout(() => {
      if (generation !== endGenerationRef.current) return;
      endTimerRef.current = null;
      const finished = pendingSilenceRef.current;
      pendingSilenceRef.current = null;
      setIsSilencePlaying(false);
      setIsSilencePaused(false);
      if (finished && autoAdvanceRef.current) finished.callback();
    }, pending.remainingMs);
    return true;
  }, []);

  const scheduleAfterSilence = useCallback((silenceMs: number, callback: () => void) => {
    cancelEndTimer();
    if (silenceMs <= 0) {
      callback();
      return;
    }
    pendingSilenceRef.current = {
      remainingMs: silenceMs,
      startedAt: null,
      callback,
    };
    startPendingSilence();
  }, [cancelEndTimer, startPendingSilence]);

  const requestPlayback = useCallback(() => {
    cancelEndTimer();
    autoAdvanceRef.current = true;
    setAutoAdvance(true);
    setPlayRequest((value) => value + 1);
  }, [cancelEndTimer]);

  const pauseSilence = useCallback(() => {
    const pending = pendingSilenceRef.current;
    if (!pending) {
      cancelEndTimer();
      autoAdvanceRef.current = false;
      setAutoAdvance(false);
      return;
    }

    const elapsedMs = pending.startedAt === null
      ? 0
      : Math.max(0, performance.now() - pending.startedAt);
    const remainingMs = Math.max(0, pending.remainingMs - elapsedMs);
    clearEndTimer();
    autoAdvanceRef.current = false;
    setAutoAdvance(false);
    setIsSilencePlaying(false);
    if (remainingMs > 0) {
      pendingSilenceRef.current = {...pending, remainingMs, startedAt: null};
      setIsSilencePaused(true);
    } else {
      pendingSilenceRef.current = null;
      setIsSilencePaused(false);
    }
  }, [cancelEndTimer, clearEndTimer]);

  const resumeSilence = useCallback(() => {
    if (!pendingSilenceRef.current) {
      requestPlayback();
      return;
    }
    autoAdvanceRef.current = true;
    setAutoAdvance(true);
    startPendingSilence();
  }, [requestPlayback, startPendingSilence]);

  const selectEntry = useCallback((index: number, phase?: PlaybackPhase) => {
    if (index < 0 || index >= entries.length) return;
    cancelEndTimer();
    const nextPhase = phase || (playbackMode === "sentences" && entries[index].sentence_audio_url ? "sentence" : "word");
    setActiveIndex(index);
    setActivePhase(nextPhase);
    requestPlayback();
  }, [cancelEndTimer, entries, playbackMode, requestPlayback]);

  const moveClip = useCallback((direction: -1 | 1) => {
    if (!activeEntry || showStarred) return;
    let nextIndex = activeIndex;
    let nextPhase: PlaybackPhase = activePhase;
    if (playbackMode === "words") {
      nextIndex += direction;
      nextPhase = "word";
    } else if (playbackMode === "sentences") {
      nextIndex += direction;
      nextPhase = "sentence";
    } else if (direction > 0) {
      if (activePhase === "word" && activeEntry.sentence_audio_url) {
        nextPhase = "sentence";
      } else {
        nextIndex += 1;
        nextPhase = "word";
      }
    } else if (activePhase === "sentence") {
      nextPhase = "word";
    } else if (activeIndex > 0) {
      nextIndex -= 1;
      nextPhase = entries[nextIndex]?.sentence_audio_url ? "sentence" : "word";
    }
    if (nextIndex < 0 || nextIndex >= entries.length || (nextIndex === activeIndex && nextPhase === activePhase)) return;
    cancelEndTimer();
    setActiveIndex(nextIndex);
    setActivePhase(nextPhase);
    requestPlayback();
  }, [activeEntry, activeIndex, activePhase, cancelEndTimer, entries, playbackMode, requestPlayback, showStarred]);

  const advanceAfterPlayback = useCallback(() => {
    if (!activeEntry || activeIndex >= entries.length - 1) {
      setAutoAdvance(false);
      return;
    }
    setActiveIndex(activeIndex + 1);
    setActivePhase(playbackMode === "sentences" ? "sentence" : "word");
  }, [activeEntry, activeIndex, entries.length, playbackMode]);

  const handlePlaybackEnd = useCallback(() => {
    if (!autoAdvanceRef.current) return;
    if (playbackMode === "both" && activePhase === "word" && activeEntry?.sentence_audio_url) {
      scheduleAfterSilence(postWordSilence, () => setActivePhase("sentence"));
      return;
    }
    scheduleAfterSilence(activePhase === "word" ? postWordSilence : postSentenceSilence, advanceAfterPlayback);
  }, [activeEntry, activePhase, advanceAfterPlayback, playbackMode, postSentenceSilence, postWordSilence, scheduleAfterSilence]);

  const handlePlayingChange = useCallback((playing: boolean) => {
    setIsPlaying(playing);
    if (playing) {
      setIsSilencePlaying(false);
      setIsSilencePaused(false);
    }
  }, []);

  const togglePlayback = useCallback(() => {
    if (isPlaying) {
      setPauseRequest((value) => value + 1);
    } else if (isSilencePlaying) {
      pauseSilence();
    } else if (isSilencePaused) {
      resumeSilence();
    } else {
      requestPlayback();
    }
  }, [isPlaying, isSilencePaused, isSilencePlaying, pauseSilence, requestPlayback, resumeSilence]);

  const replayFocused = useCallback(() => {
    cancelEndTimer();
    setAutoAdvance(true);
    setReplayRequest((value) => value + 1);
  }, [cancelEndTimer]);

  const stopPlayback = useCallback(() => {
    cancelEndTimer();
    autoAdvanceRef.current = false;
    setAutoAdvance(false);
    setStopRequest((value) => value + 1);
  }, [cancelEndTimer]);

  const changePlaybackMode = useCallback((mode: PlaybackMode) => {
    cancelEndTimer();
    setPlaybackMode(mode);
    setActivePhase(mode === "sentences" && activeEntry?.sentence_audio_url ? "sentence" : "word");
    savePlaybackSettings(postWordSilence, postSentenceSilence, mode);
  }, [activeEntry, cancelEndTimer, postSentenceSilence, postWordSilence]);

  const changePostWordSilence = useCallback((value: number) => {
    setPostWordSilence(value);
    savePlaybackSettings(value, postSentenceSilence, playbackMode);
  }, [playbackMode, postSentenceSilence]);

  const changePostSentenceSilence = useCallback((value: number) => {
    setPostSentenceSilence(value);
    savePlaybackSettings(postWordSilence, value, playbackMode);
  }, [playbackMode, postWordSilence]);

  const toggleMark = useCallback(async (key: "known" | "flagged") => {
    if (!activeEntry) return;
    const next = {
      known: !!activeEntry.mark?.known,
      flagged: !!activeEntry.mark?.flagged,
    };
    next[key] = !next[key];
    try {
      await updateMark(activeEntry.entry_id, next, selectedBook);
      setEntries((current) => current.map((entry) => entry.entry_id === activeEntry.entry_id
        ? {...entry, mark: {...entry.mark, ...next}}
        : entry));
      setDetail((current) => current && current.entry_id === activeEntry.entry_id
        ? {...current, mark: {...current.mark, ...next}}
        : current);
      await refreshCatalog();
      setStatus(`${activeEntry.kanji} is ${next[key] ? key : `not ${key}`}.`);
    } catch (error: unknown) {
      setStatus(error instanceof Error ? error.message : "Could not update the study mark.");
    }
  }, [activeEntry, refreshCatalog, selectedBook]);

  const toggleSentenceStar = useCallback(async () => {
    if (!activeEntry) return;
    const position = activeEntry.sentence_position ?? 0;
    try {
      const payload = await updateExampleStar(activeEntry.entry_id, position, !activeEntry.sentence_starred, selectedBook);
      setEntries((current) => current.map((entry) => entry.entry_id === activeEntry.entry_id
        ? {...entry, sentence_starred: payload.starred}
        : entry));
      setDetail((current) => current && current.entry_id === activeEntry.entry_id
        ? {...current, sentence_starred: payload.starred}
        : current);
      setStatus(payload.starred ? "Main sentence starred." : "Main sentence unstarred.");
      if (showStarred) {
        const starred = await getStarredSentences(selectedBook, selectedUnit ?? undefined);
        setStarredSentences(starred.items);
      }
    } catch (error: unknown) {
      setStatus(error instanceof Error ? error.message : "Could not update the sentence star.");
    }
  }, [activeEntry, selectedBook, selectedUnit, showStarred]);

  const toggleCoverAll = useCallback(() => {
    setCoveredEntryIds((current) => {
      const next = new Set(current);
      if (allVisibleCovered) entries.forEach((entry) => next.delete(entry.entry_id));
      else entries.forEach((entry) => next.add(entry.entry_id));
      return next;
    });
  }, [allVisibleCovered, entries]);

  const exportFlaggedAudio = useCallback(async () => {
    if (selectedUnit === null) {
      setStatus("Choose a section before exporting flagged audio.");
      return;
    }
    try {
      const payload = await exportUnitFlaggedAudio(selectedUnit, selectedBook);
      const link = document.createElement("a");
      link.href = payload.audio_url;
      link.download = payload.file_name || "flagged-audio.mp3";
      document.body.appendChild(link);
      link.click();
      link.remove();
      setStatus(`Exported ${payload.word_count} flagged words from ${unitLabel(units.find((item) => item.number === payload.unit))}.`);
    } catch (error: unknown) {
      setStatus(error instanceof Error ? error.message : "Could not export flagged audio.");
    }
  }, [selectedBook, selectedUnit, units]);

  const canPrevious = !showStarred && (activeIndex > 0 || (playbackMode === "both" && activePhase === "sentence"));
  const canNext = !showStarred && (activeIndex < entries.length - 1 || (playbackMode === "both" && activePhase === "word" && !!activeEntry?.sentence_audio_url));
  const playbackActive = isPlaying || isSilencePlaying;

  const renderStarredView = () => (
    <section className="react-starred-view" aria-label="Starred sentence review">
      <aside className="react-starred-filter">
        <div className="section-label">Section filter</div>
        <button type="button" className={!selectedUnit ? "is-selected" : ""} onClick={() => setSelectedUnit(null)}>
          <strong>All sections</strong><span>{starredSentences.length}</span>
        </button>
        {units.map((item) => (
          <button type="button" key={item.number} className={selectedUnit === item.number ? "is-selected" : ""} onClick={() => setSelectedUnit(item.number)}>
            <strong>{unitLabel(item)}</strong><span>{starredSentences.filter((sentence) => sentence.unit.number === item.number).length}</span>
          </button>
        ))}
      </aside>
      <section className="react-starred-list-panel">
        <div className="react-starred-heading"><div><span className="eyebrow">SENTENCE REVIEW</span><h2>Starred sentences</h2></div><span>{starredSentences.length} shown</span></div>
        {starredSentences.length ? starredSentences.map((item, index) => {
          const key = `${item.entry_id}:${item.position}`;
          return <button type="button" key={key} className={`react-starred-row${key === selectedStarredKey ? " is-selected" : ""}`} onClick={() => setSelectedStarredKey(key)}><span>{String(index + 1).padStart(2, "0")}</span><strong>{item.text}</strong><small>{item.translation_en || item.translation_zh}</small><em>★</em></button>;
        }) : <p className="react-empty">No starred sentences yet.</p>}
      </section>
      <aside className="react-starred-detail">
        {selectedStarred ? <>
          <span className="eyebrow">{unitLabel(selectedStarred.unit)} · #{selectedStarred.source_index}</span>
          <h2>{selectedStarred.word}</h2>
          <p className="react-starred-sentence">{selectedStarred.text}</p>
          <p>{selectedStarred.translation_en || selectedStarred.translation_zh}</p>
          <p className="react-meaning">{selectedStarred.meaning_en || selectedStarred.meaning_zh}</p>
          {selectedStarred.explanation_md ? <details open><summary>Sentence explanation</summary><MarkdownContent value={selectedStarred.explanation_md} /></details> : null}
          <button type="button" onClick={() => {
            const index = entries.findIndex((entry) => entry.entry_id === selectedStarred.entry_id);
            if (index >= 0) {
              setShowStarred(false);
              selectEntry(index, "sentence");
            } else {
              setStatus("The starred sentence is outside the current filtered list. Clear the search or filter to focus it.");
            }
          }}>Focus in study wall</button>
        </> : <p className="react-empty">Pick a starred sentence to review it here.</p>}
      </aside>
    </section>
  );

  return (
    <main className="react-shell">
      <header className="react-header">
        <div className="react-brand">
          <span className="eyebrow">N2 VOCABULARY · REACT PREVIEW</span>
          <h1>{currentBook?.title || "スタディウォール"}</h1>
          <div className="react-summary-meta">
            {summary ? <><span>{summary.entries} entries</span><span>{summary.units} sections</span><span>{summary.known} known</span><span>{summary.flagged} flagged</span><span>{summary.unmarked} unmarked</span></> : <span>Loading vocabulary…</span>}
          </div>
        </div>
        <div className="react-pickers">
          <label><span>Book</span><select value={selectedBook} onChange={(event) => { setSelectedBook(event.target.value); setSelectedUnit(null); setShowStarred(false); }}><option value="">Choose book</option>{books.map((book) => <option key={book.code} value={book.code}>{book.code} · {book.title}</option>)}</select></label>
          <label><span>Section</span><select value={selectedUnit ?? ""} onChange={(event) => setSelectedUnit(event.target.value ? Number(event.target.value) : null)}><option value="">All sections</option>{units.map((item) => <option key={item.number} value={item.number}>{unitLabel(item)} · {item.entry_count} words</option>)}</select></label>
        </div>
      </header>

      <nav className="react-unit-strip" aria-label="Sections">
        <button type="button" className={selectedUnit === null ? "is-selected" : ""} onClick={() => setSelectedUnit(null)}>All</button>
        {units.map((item) => <button type="button" key={item.number} className={selectedUnit === item.number ? "is-selected" : ""} onClick={() => setSelectedUnit(item.number)} title={`${item.title} · ${item.entry_count} words`}>{unitLabel(item)}</button>)}
      </nav>

      <section className="react-toolbar" aria-label="Study controls">
        <div className="react-toolbar-search"><input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search kanji, reading, meaning, sentence…" aria-label="Search vocabulary" /></div>
        <div className="react-pill-group" role="group" aria-label="Study state filter">
          {(["all", "unmarked", "known", "flagged"] as FilterState[]).map((filter) => <button type="button" key={filter} className={`${filterState === filter ? "is-selected " : ""}react-pill react-pill-${filter}`} onClick={() => { setFilterState(filter); setShowStarred(false); }}>{filter[0].toUpperCase() + filter.slice(1)}{filter !== "all" && summary ? <small>{summary[filter]}</small> : null}</button>)}
        </div>
        <div className="react-toolbar-actions">
          <button type="button" onClick={toggleCoverAll} disabled={!entries.length} aria-pressed={allVisibleCovered}>{allVisibleCovered ? "Uncover all" : "Cover all"}</button>
          <button type="button" onClick={togglePlayback} disabled={!target} aria-pressed={playbackActive}>{playbackActive ? "Pause visible" : isSilencePaused ? "Resume visible" : "Play visible"}</button>
          <button type="button" className={showStarred ? "is-selected" : ""} onClick={() => setShowStarred((current) => !current)} aria-pressed={showStarred}>★ Starred sentences</button>
          <a href="/audio-review.html">Audio text review</a>
          <button type="button" onClick={() => void exportFlaggedAudio()} disabled={selectedUnit === null}>Export flagged audio</button>
          <a href="/">Classic study wall</a>
          <a href="/study-wall-rail.html">Current rail</a>
          <button type="button" onClick={() => setBlurred((current) => !current)} aria-pressed={blurred} title="B: blur / reveal the study content">B</button>
          <button type="button" className="react-settings-button" onClick={() => setSettingsOpen(true)} aria-label="Open playback settings" title="Playback settings">⚙</button>
        </div>
      </section>

      {status ? <div className="react-status" role="status" aria-live="polite">{status}</div> : null}

      <div className={`react-content-scroll${blurred ? " is-blurred" : ""}`}>
        {showStarred ? renderStarredView() : <div className="react-layout" ref={layoutRef} style={{gridTemplateColumns: `${listWidth}px 12px minmax(0, 1fr)`}}>
          <section className="react-list" aria-label="Vocabulary playback list">
            {entriesLoading ? <p className="react-empty">Loading vocabulary…</p> : entries.length ? entries.map((entry, index) => <button key={entry.entry_id} ref={index === activeIndex ? activeRef : null} className={`${index === activeIndex ? "is-active " : ""}${coveredEntryIds.has(entry.entry_id) ? "is-covered" : ""}`} aria-current={index === activeIndex ? "true" : undefined} onClick={() => selectEntry(index)}><span className="react-row-index">{String(index + 1).padStart(3, "0")}</span><span className="react-row-kanji">{entry.kanji}</span><span className="react-row-status" aria-label={`${entry.mark?.known ? "known" : ""}${entry.mark?.flagged ? " flagged" : ""}`}>{entry.mark?.known ? "✓" : ""}{entry.mark?.flagged ? " ⚑" : ""}</span></button>) : <p className="react-empty">No words match the current filters.</p>}
          </section>
          <button className="react-divider" type="button" role="separator" aria-orientation="vertical" aria-label="Adjust playback list width" aria-valuemin={220} aria-valuemax={620} aria-valuenow={listWidth} tabIndex={0} onPointerDown={(event) => { event.preventDefault(); event.currentTarget.setPointerCapture(event.pointerId); setDraggingDivider(true); }} onKeyDown={(event) => { if (event.key === "ArrowLeft") setListWidth((value) => Math.max(220, value - (event.shiftKey ? 50 : 20))); else if (event.key === "ArrowRight") setListWidth((value) => Math.min(620, value + (event.shiftKey ? 50 : 20))); else return; event.preventDefault(); }}> </button>
          <section ref={currentRef} className={`react-current${activeEntry && coveredEntryIds.has(activeEntry.entry_id) ? " is-covered" : ""}`} aria-live="polite" aria-label="Current vocabulary item">
            {activeEntry ? <>
              <span className="eyebrow">{activeEntry.book_code} #{String(activeEntry.source_index).padStart(3, "0")} · {unitLabel(activeEntry.unit)}</span>
              <h2>{activeEntry.kanji}</h2>
              {coveredEntryIds.has(activeEntry.entry_id) ? <p className="react-covered-note">Answers covered. Press Uncover all or Cover all to reveal the study details.</p> : <>
                <ruby>{activeEntry.kanji}<rt>{activeEntry.reading}</rt></ruby>
                <p className="react-meaning">{activeEntry.meaning_en || activeEntry.meaning_zh}</p>
                <div className="react-current-actions">
                  <button type="button" onClick={() => { setActivePhase("word"); requestPlayback(); }} className={activePhase === "word" ? "is-selected" : ""}>Word</button>
                  <button type="button" onClick={() => { setActivePhase("sentence"); requestPlayback(); }} className={activePhase === "sentence" ? "is-selected" : ""} disabled={!activeEntry.sentence_audio_url}>Sentence</button>
                  <button type="button" className={activeEntry.mark?.known ? "is-on" : ""} onClick={() => void toggleMark("known")} aria-pressed={!!activeEntry.mark?.known}>✓ Known</button>
                  <button type="button" className={activeEntry.mark?.flagged ? "is-on" : ""} onClick={() => void toggleMark("flagged")} aria-pressed={!!activeEntry.mark?.flagged}>⚑ Flag</button>
                  <button type="button" className={activeEntry.sentence_starred ? "is-on" : ""} onClick={() => void toggleSentenceStar()} aria-pressed={!!activeEntry.sentence_starred}>{activeEntry.sentence_starred ? "★" : "☆"} Sentence</button>
                </div>
                {detail?.sentence ? <div className="react-sentence"><strong>{detail.sentence}</strong><span>{detail.sentence_translation_en || detail.sentence_translation_zh}</span></div> : null}
                {detail?.explanation_md ? <details><summary>Sentence explanation</summary><MarkdownContent value={detail.explanation_md} /></details> : null}
              </>}
            </> : <p className="react-empty">Loading vocabulary…</p>}
          </section>
        </div>}
      </div>

      <RailPlayer
        target={target}
        autoPlay={autoAdvance}
        isPlaybackActive={playbackActive}
        isSilencePlaying={isSilencePlaying}
        onPlayingChange={handlePlayingChange}
        playRequest={playRequest}
        replayRequest={replayRequest}
        pauseRequest={pauseRequest}
        stopRequest={stopRequest}
        onEnded={handlePlaybackEnd}
        onTogglePlayback={togglePlayback}
        onReplay={replayFocused}
        onPrevious={() => moveClip(-1)}
        onNext={() => moveClip(1)}
        onStop={stopPlayback}
        canPrevious={canPrevious}
        canNext={canNext}
      />

      {settingsOpen ? <div className="react-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setSettingsOpen(false); }}>
        <section className="react-settings-modal" role="dialog" aria-modal="true" aria-labelledby="react-settings-title">
          <div className="react-settings-head"><div><span className="eyebrow">PLAYBACK</span><h2 id="react-settings-title">Playback settings</h2></div><button type="button" onClick={() => setSettingsOpen(false)} aria-label="Close playback settings">×</button></div>
          <div className="react-settings-body">
            <div className="react-setting-copy"><span>Playback</span><p>Choose what plays as the focused list advances.</p></div>
            <div className="react-setting-options" role="radiogroup" aria-label="Playback mode">
              {(["words", "sentences", "both"] as PlaybackMode[]).map((mode) => <button type="button" key={mode} className={playbackMode === mode ? "is-selected" : ""} role="radio" aria-checked={playbackMode === mode} onClick={() => changePlaybackMode(mode)}>{mode === "words" ? "Words only" : mode === "sentences" ? "Sentences only" : "Word + sentence"}</button>)}
            </div>
            <div className="react-setting-copy"><label htmlFor="react-post-word-silence">Silence after word</label><output htmlFor="react-post-word-silence">{postWordSilence} ms</output><p>Wait this long after a word clip before its sentence or the next word starts.</p></div>
            <input id="react-post-word-silence" type="range" min="0" max="3000" step="100" value={postWordSilence} onChange={(event) => changePostWordSilence(Number(event.target.value))} />
            <div className="react-setting-scale" aria-hidden="true"><span>None</span><span>3 seconds</span></div>
            <div className="react-setting-copy"><label htmlFor="react-post-sentence-silence">Silence after sentence</label><output htmlFor="react-post-sentence-silence">{postSentenceSilence} ms</output><p>Wait this long before the next word starts during visible-list playback.</p></div>
            <input id="react-post-sentence-silence" type="range" min="0" max="3000" step="100" value={postSentenceSilence} onChange={(event) => changePostSentenceSilence(Number(event.target.value))} />
            <div className="react-setting-scale" aria-hidden="true"><span>None</span><span>3 seconds</span></div>
            <button type="button" className="react-settings-reset" onClick={() => { setPostWordSilence(DEFAULT_SILENCE_MS); setPostSentenceSilence(DEFAULT_SILENCE_MS); setPlaybackMode("both"); savePlaybackSettings(DEFAULT_SILENCE_MS, DEFAULT_SILENCE_MS, "both"); }}>Reset to defaults</button>
          </div>
        </section>
      </div> : null}
    </main>
  );
}
