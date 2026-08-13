import {useCallback, useEffect, useMemo, useRef, useState} from "react";

import {resolveReviewEntries, updateExampleStar} from "../../api";
import type {Entry} from "../../types";
import {PlaybackSettingsModal} from "../player/PlaybackSettingsModal";
import {RailPlayer} from "../player/RailPlayer";
import {useStudyPlayback} from "../player/useStudyPlayback";
import {nextGoodIntervalDays} from "./reviewScheduler.mjs";
import {StudyWallView} from "./StudyWallView";
import type {ReviewGrade, StudyCardState, StudyStateStore} from "./studyStateTypes";

interface ReviewAppProps {
  store: StudyStateStore;
  accountEmail?: string;
}

export function ReviewApp({store, accountEmail}: ReviewAppProps) {
  const [sessionCards] = useState<StudyCardState[]>(() => store.dueCards());
  const [entries, setEntries] = useState<Entry[]>([]);
  const [position, setPosition] = useState(0);
  const [completedItems, setCompletedItems] = useState<Set<string>>(() => new Set());
  const [pendingGrade, setPendingGrade] = useState<ReviewGrade>("again");
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const current = entries[position];
  const currentCard = current ? store.load().cards[current.item_uuid] : undefined;
  // Start the first resolved due card through the same navigation path as a
  // later row jump. This also makes initial autoplay explicit for this
  // dedicated route rather than relying only on the player target effect.
  const playAfterFocusRef = useRef<number | null>(0);
  const playAfterCommitRef = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const resolved: Entry[] = [];
      for (let offset = 0; offset < sessionCards.length; offset += 100) {
        const page = sessionCards.slice(offset, offset + 100);
        const response = await resolveReviewEntries(page.map(card => ({
          item_uuid: card.item_uuid,
          preferred_book_code: card.preferred_book_code,
          preferred_source_index: card.preferred_source_index,
        })));
        const byUuid = new Map(response.items.map(entry => [entry.item_uuid, entry]));
        for (const card of page) {
          const entry = byUuid.get(card.item_uuid);
          if (entry) resolved.push({...entry, mark: {...entry.mark, known: card.known, flagged: card.flagged}});
        }
      }
      if (!cancelled) setEntries(resolved);
    }
    load().catch(error => { if (!cancelled) setStatus(error instanceof Error ? error.message : "Could not load due cards."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [sessionCards]);

  useEffect(() => setPendingGrade("again"), [current?.item_uuid]);

  const commitAndAdvance = useCallback(async () => {
    if (!current) return;
    try {
      const updatedCard = await store.grade(current.item_uuid, pendingGrade);
      setEntries(previous => previous.map(entry => entry.item_uuid === current.item_uuid
        ? {...entry, mark: {...entry.mark, known: updatedCard.known, flagged: updatedCard.flagged}}
        : entry));
      setCompletedItems(previous => {
        const next = new Set(previous);
        next.add(current.item_uuid);
        return next;
      });
      setPosition(value => {
        const next = value + 1;
        // Advancing a review card is explicit navigation, so keep autoplay
        // consistent with the regular wall in both run modes.
        if (next < entries.length) playAfterCommitRef.current = next;
        return next;
      });
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Could not save the review grade.");
    }
  }, [current, entries.length, pendingGrade, store]);

  const activeEntries = useMemo(() => current ? [current] : [], [current]);
  const playback = useStudyPlayback({
    entries: activeEntries,
    showStarred: false,
    onCompleteCard: entry => { void store.recordPlayed(entry).catch(error => setStatus(error instanceof Error ? error.message : "Could not save playback.")); },
    onConsecutiveSequenceComplete: () => { void commitAndAdvance(); },
  });
  const playCurrentReviewEntry = useCallback(() => {
    if (!current) return;
    const phase = playback.playbackMode === "sentences" && current.sentence_audio_url ? "sentence" : "word";
    playback.selectPhase(phase);
  }, [current, playback.playbackMode, playback.selectPhase]);
  const selectReviewEntry = useCallback((index: number) => {
    if (index < 0 || index >= entries.length) return;
    playback.stopPlayback();
    playAfterFocusRef.current = index;
    setPosition(index);
    setStatus("");
  }, [entries.length, playback.stopPlayback]);
  useEffect(() => {
    if (!current || playAfterFocusRef.current !== position) return;
    playAfterFocusRef.current = null;
    playCurrentReviewEntry();
  }, [current, playCurrentReviewEntry, position]);
  useEffect(() => {
    if (!current || playAfterCommitRef.current !== position) return;
    playAfterCommitRef.current = null;
    playCurrentReviewEntry();
  }, [current, playCurrentReviewEntry, position]);

  const toggleSentenceStar = useCallback(async () => {
    if (!current) return;
    const position = current.sentence_position ?? 0;
    try {
      const payload = await updateExampleStar(current.entry_id, position, !current.sentence_starred, current.book_code);
      setEntries(previous => previous.map(entry => entry.item_uuid === current.item_uuid
        ? {...entry, sentence_starred: payload.starred}
        : entry));
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Could not update the sentence star.");
    }
  }, [current]);

  const next = useCallback(() => {
    if (!current) return;
    if (playback.playbackMode === "both" && playback.activePhase === "word" && current.sentence_audio_url) {
      playback.selectPhase("sentence");
      return;
    }
    void commitAndAdvance();
  }, [commitAndAdvance, current, playback]);

  const previous = useCallback(() => {
    if (!current) return;
    if (playback.playbackMode === "both" && playback.activePhase === "sentence") {
      playback.moveClip(-1);
      return;
    }
    if (position > 0) selectReviewEntry(position - 1);
  }, [current, playback, position, selectReviewEntry]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement || event.target instanceof HTMLSelectElement) return;
      const grade = event.key === "1" ? "again" : event.key === "2" || event.key.toLowerCase() === "f" ? "hard" : event.key === "3" || event.key === "Enter" || event.key.toLowerCase() === "k" ? "good" : undefined;
      if (!grade) return;
      event.preventDefault();
      setPendingGrade(grade);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const remaining = Math.max(0, entries.length - completedItems.size);
  const completed = completedItems.size;
  const nextDue = store.nextDueAt();

  return <main className="react-shell review-shell">
    <header className="react-header review-header">
      <div className="react-brand"><span className="eyebrow">SPACED REVIEW · {accountEmail || "GUEST"}</span><h1>Review due vocabulary</h1><div className="react-summary-meta"><span>{entries.length} due</span><span>{completed} completed</span><span>{remaining} remaining</span></div></div>
      <div className="review-header-actions"><a href="/">Return to study wall</a><button type="button" onClick={() => setSettingsOpen(true)}>Playback settings</button></div>
    </header>
    {status ? <div className="react-status" role="alert">{status}</div> : null}
    {loading ? <p className="react-empty">Loading due cards…</p> : current ? <>
      <section className="review-grade-bar" aria-label="Pending review grade">
        <span>Pending grade</span>
        <button type="button" className={pendingGrade === "again" ? "is-selected" : ""} onClick={() => setPendingGrade("again")}>1 · Again · 10m</button>
        <button type="button" className={pendingGrade === "hard" ? "is-selected" : ""} onClick={() => setPendingGrade("hard")}>2 · ⚑ Hard · 1d</button>
        <button type="button" className={pendingGrade === "good" ? "is-selected" : ""} onClick={() => setPendingGrade("good")}>3 · ✓ Good · {nextGoodIntervalDays(currentCard?.good_step ?? 0)}d</button>
      </section>
      <div className="react-content-scroll review-content"><StudyWallView activeEntry={current} activeIndex={position} activePhase={playback.activePhase} bookCode={current.book_code} coveredEntryIds={new Set()} detail={current} entries={entries} entriesLoading={false} onSelectEntry={selectReviewEntry} onSelectPhase={playback.selectPhase} onToggleMark={key => setPendingGrade(key === "flagged" ? "hard" : "good")} onToggleSentenceStar={toggleSentenceStar} /></div>
      <RailPlayer target={playback.target} autoPlay={playback.autoAdvance} isPlaybackActive={playback.playbackActive} isSilencePlaying={playback.isSilencePlaying} playbackRunMode={playback.playbackRunMode} onPlayingChange={playback.handlePlayingChange} playRequest={playback.playRequest} replayRequest={playback.replayRequest} pauseRequest={playback.pauseRequest} stopRequest={playback.stopRequest} onEnded={playback.handlePlaybackEnd} onTogglePlayback={playback.togglePlayback} onTogglePlaybackRunMode={playback.togglePlaybackRunMode} onReplay={playback.replayFocused} onPrevious={previous} onNext={next} onStop={playback.stopPlayback} canPrevious={position > 0 || (playback.playbackMode === "both" && playback.activePhase === "sentence")} canNext={true} />
    </> : <section className="review-empty"><h2>Review complete</h2><p>No more cards from this due snapshot.</p>{nextDue ? <p>Next scheduled review: {new Date(nextDue).toLocaleString()}</p> : <p>Play vocabulary on the study wall to create review tasks.</p>}<a href="/">Return to study wall</a></section>}
    {settingsOpen ? <PlaybackSettingsModal playbackMode={playback.playbackMode} postSentenceSilence={playback.postSentenceSilence} postWordSilence={playback.postWordSilence} onChangePlaybackMode={playback.changePlaybackMode} onChangePostSentenceSilence={playback.changePostSentenceSilence} onChangePostWordSilence={playback.changePostWordSilence} onClose={() => setSettingsOpen(false)} onReset={playback.resetPlaybackSettings} /> : null}
  </main>;
}
