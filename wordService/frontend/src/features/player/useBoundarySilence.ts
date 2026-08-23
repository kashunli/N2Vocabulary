import { useCallback, useEffect, useRef, useState } from "react";

type PendingSilence = {
  remainingMs: number;
  startedAt: number | null;
  callback: () => void;
};

type BooleanRef = {
  current: boolean;
};

/**
 * Owns the lifecycle of the intentional gap between study clips.
 *
 * Playback policy stays in `useStudyPlayback`; this hook only manages timer
 * identity, pause/resume bookkeeping, and the learner-visible silence state.
 */
export function useBoundarySilence(advanceEnabledRef: BooleanRef) {
  const [isSilencePlaying, setIsSilencePlaying] = useState(false);
  const [isSilencePaused, setIsSilencePaused] = useState(false);
  const timerRef = useRef<number | null>(null);
  const timerGenerationRef = useRef(0);
  const pendingRef = useRef<PendingSilence | null>(null);

  const clearTimer = useCallback(() => {
    timerGenerationRef.current += 1;
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const cancel = useCallback(() => {
    clearTimer();
    pendingRef.current = null;
    setIsSilencePlaying(false);
    setIsSilencePaused(false);
  }, [clearTimer]);

  const start = useCallback(() => {
    const pending = pendingRef.current;
    if (!pending) return false;

    if (pending.remainingMs <= 0) {
      pendingRef.current = null;
      setIsSilencePlaying(false);
      setIsSilencePaused(false);
      if (advanceEnabledRef.current) pending.callback();
      return true;
    }

    pending.startedAt = performance.now();
    setIsSilencePlaying(true);
    setIsSilencePaused(false);
    const generation = timerGenerationRef.current;
    timerRef.current = window.setTimeout(() => {
      if (generation !== timerGenerationRef.current) return;
      timerRef.current = null;
      const finished = pendingRef.current;
      pendingRef.current = null;
      setIsSilencePlaying(false);
      setIsSilencePaused(false);
      if (finished && advanceEnabledRef.current) finished.callback();
    }, pending.remainingMs);
    return true;
  }, [advanceEnabledRef]);

  const schedule = useCallback((silenceMs: number, callback: () => void) => {
    cancel();
    if (silenceMs <= 0) {
      callback();
      return;
    }
    pendingRef.current = {remainingMs: silenceMs, startedAt: null, callback};
    start();
  }, [cancel, start]);

  const pause = useCallback(() => {
    const pending = pendingRef.current;
    if (!pending) {
      cancel();
      return false;
    }

    const elapsedMs = pending.startedAt === null
      ? 0
      : Math.max(0, performance.now() - pending.startedAt);
    const remainingMs = Math.max(0, pending.remainingMs - elapsedMs);
    clearTimer();
    setIsSilencePlaying(false);
    if (remainingMs > 0) {
      pendingRef.current = {...pending, remainingMs, startedAt: null};
      setIsSilencePaused(true);
    } else {
      pendingRef.current = null;
      setIsSilencePaused(false);
    }
    return true;
  }, [cancel, clearTimer]);

  const hideState = useCallback(() => {
    setIsSilencePlaying(false);
    setIsSilencePaused(false);
  }, []);

  useEffect(() => () => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
  }, []);

  return {
    cancel,
    clearTimer,
    hideState,
    isSilencePaused,
    isSilencePlaying,
    pause,
    resume: start,
    schedule,
  };
}
