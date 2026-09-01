import { useCallback, useEffect, useRef, useState } from "react";

import {
  clampAudioPosition,
  playableRange,
  playbackPosition,
} from "./audioClock.mjs";

interface PlayRangeOptions {
  start: number;
  end: number;
  offset: number;
  segmentId: string;
}

interface ActiveRange {
  start: number;
  end: number;
  segmentId: string;
}

// Decoded PCM buffers are far larger than the compressed MP3s (roughly
// 0.7 MB/second stereo float32), so an unbounded cache would eat memory across
// a long study session. An LRU capped at 40 clips (about a screen of cards,
// word and sentence each) keeps the cache flat while covering repeated plays.
const MAX_CACHED_AUDIO_BUFFERS = 40;
const cachedAudioBuffers = new Map<string, AudioBuffer>();

function audioCacheKey(audioUrl: string, audioId: number | undefined) {
  // The URL in a list payload is intentionally unversioned for a cheap bulk
  // response. Prefer the persisted ID so replacing an MP3 cannot reuse the
  // previous decoded PCM buffer when that path stays the same.
  return audioId === undefined ? `url:${audioUrl}` : `id:${audioId}`;
}

function loadDecodedAudio(
  audioUrl: string,
  audioId: number | undefined,
  controller: AbortController,
  context: AudioContext,
): Promise<AudioBuffer> {
  const cacheKey = audioCacheKey(audioUrl, audioId);
  const cached = cachedAudioBuffers.get(cacheKey);
  if (cached) {
    // Reinsert so Map iteration order keeps the cache LRU.
    cachedAudioBuffers.delete(cacheKey);
    cachedAudioBuffers.set(cacheKey, cached);
    return Promise.resolve(cached);
  }
  return (async () => {
    const response = await fetch(audioUrl, { signal: controller.signal });
    if (!response.ok) throw new Error("audio request failed");
    const encodedAudio = await response.arrayBuffer();
    const decodedAudio = await context.decodeAudioData(encodedAudio);
    if (cachedAudioBuffers.size >= MAX_CACHED_AUDIO_BUFFERS) {
      const oldestKey = cachedAudioBuffers.keys().next().value;
      if (oldestKey !== undefined) cachedAudioBuffers.delete(oldestKey);
    }
    cachedAudioBuffers.set(cacheKey, decodedAudio);
    return decodedAudio;
  })();
}

export function useAudioBufferPlayer(
  audioUrl: string | undefined,
  audioId: number | undefined,
  onRangeEnd: (segmentId: string) => void,
) {
  const requestedUrlRef = useRef(audioUrl);
  requestedUrlRef.current = audioUrl;
  const requestedAudioIdRef = useRef(audioId);
  requestedAudioIdRef.current = audioId;
  const contextRef = useRef<AudioContext | null>(null);
  const bufferRef = useRef<AudioBuffer | null>(null);
  const loadedUrlRef = useRef("");
  const loadedAudioIdRef = useRef<number | undefined>(undefined);
  const decodePromiseRef = useRef<Promise<AudioBuffer> | null>(null);
  const sourceRef = useRef<AudioBufferSourceNode | null>(null);
  const activeRangeRef = useRef<ActiveRange | null>(null);
  const currentTimeRef = useRef(0);
  const anchorAudioTimeRef = useRef(0);
  const anchorContextTimeRef = useRef(0);
  const isPlayingRef = useRef(false);
  const animationFrameRef = useRef<number | null>(null);
  const requestNumberRef = useRef(0);
  const onRangeEndRef = useRef(onRangeEnd);
  onRangeEndRef.current = onRangeEnd;

  const [audioBuffer, setAudioBuffer] = useState<AudioBuffer | null>(null);
  // Keep the URL that produced the visible buffer in React state as well as
  // the ref used by the playback primitives.  The URL effect clears the old
  // buffer asynchronously after RailPlayer has selected a new target, so a
  // consumer must be able to distinguish a ready new buffer from a stale one.
  const [loadedAudioUrl, setLoadedAudioUrl] = useState<string>();
  const [loadedAudioId, setLoadedAudioId] = useState<number>();
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  const publishCurrentTime = useCallback((value: number) => {
    currentTimeRef.current = value;
    setCurrentTime(value);
  }, []);

  const cancelAnimation = useCallback(() => {
    if (animationFrameRef.current !== null) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
  }, []);

  const detachSource = useCallback(() => {
    const source = sourceRef.current;
    sourceRef.current = null;
    if (!source) return;
    source.onended = null;
    try {
      source.stop();
    } catch {
      // A source that already ended is harmless and cannot be stopped twice.
    }
    source.disconnect();
  }, []);

  const exactCurrentTime = useCallback(() => {
    const context = contextRef.current;
    const range = activeRangeRef.current;
    if (!context || !range || !isPlayingRef.current) return currentTimeRef.current;
    return playbackPosition(
      anchorAudioTimeRef.current,
      anchorContextTimeRef.current,
      context.currentTime,
      range.end,
    );
  }, []);

  const animate = useCallback(() => {
    cancelAnimation();
    const update = () => {
      if (!isPlayingRef.current) {
        animationFrameRef.current = null;
        return;
      }
      publishCurrentTime(exactCurrentTime());
      animationFrameRef.current = requestAnimationFrame(update);
    };
    animationFrameRef.current = requestAnimationFrame(update);
  }, [cancelAnimation, exactCurrentTime, publishCurrentTime]);

  useEffect(() => {
    requestNumberRef.current += 1;
    cancelAnimation();
    detachSource();
    isPlayingRef.current = false;
    activeRangeRef.current = null;
    bufferRef.current = null;
    loadedUrlRef.current = "";
    loadedAudioIdRef.current = undefined;
    decodePromiseRef.current = null;
    publishCurrentTime(0);
    setAudioBuffer(null);
    setLoadedAudioUrl(undefined);
    setLoadedAudioId(undefined);
    setIsPlaying(false);
    setLoadFailed(false);

    if (!audioUrl) return undefined;

    const controller = new AbortController();
    const context = new AudioContext();
    contextRef.current = context;
    const decodePromise = loadDecodedAudio(audioUrl, audioId, controller, context).then((decodedAudio) => {
      if (
        controller.signal.aborted
        || requestedUrlRef.current !== audioUrl
        || requestedAudioIdRef.current !== audioId
      ) {
        throw new DOMException("Audio load was superseded", "AbortError");
      }
      bufferRef.current = decodedAudio;
      loadedUrlRef.current = audioUrl;
      loadedAudioIdRef.current = audioId;
      setAudioBuffer(decodedAudio);
      setLoadedAudioUrl(audioUrl);
      setLoadedAudioId(audioId);
      return decodedAudio;
    });
    decodePromiseRef.current = decodePromise;
    void decodePromise.catch((reason) => {
      if (!(reason instanceof DOMException && reason.name === "AbortError")) {
        setLoadFailed(true);
      }
    });

    return () => {
      controller.abort();
      requestNumberRef.current += 1;
      cancelAnimation();
      detachSource();
      if (contextRef.current === context) contextRef.current = null;
      void context.close();
    };
  }, [audioId, audioUrl, cancelAnimation, detachSource, publishCurrentTime]);

  const playRange = useCallback(async ({
    start,
    end,
    offset,
    segmentId,
  }: PlayRangeOptions) => {
    const requestNumber = ++requestNumberRef.current;
    const expectedUrl = requestedUrlRef.current;
    const expectedAudioId = requestedAudioIdRef.current;
    let buffer = bufferRef.current;
    if (
      !buffer
      || loadedUrlRef.current !== expectedUrl
      || loadedAudioIdRef.current !== expectedAudioId
    ) {
      const pendingDecode = decodePromiseRef.current;
      if (!pendingDecode) throw new Error("audio is not ready");
      buffer = await pendingDecode;
    }
    const context = contextRef.current;
    if (
      !context
      || expectedUrl !== requestedUrlRef.current
      || expectedAudioId !== requestedAudioIdRef.current
      || requestNumber !== requestNumberRef.current
    ) return;

    await context.resume();
    if (
      expectedUrl !== requestedUrlRef.current
      || expectedAudioId !== requestedAudioIdRef.current
      || requestNumber !== requestNumberRef.current
    ) return;

    const range = playableRange(start, end, buffer.duration);
    const safeOffset = Math.min(range.end, Math.max(range.start, offset));
    cancelAnimation();
    detachSource();
    if (range.end - safeOffset <= 0.001) {
      activeRangeRef.current = null;
      publishCurrentTime(range.end);
      setIsPlaying(false);
      isPlayingRef.current = false;
      return;
    }

    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(context.destination);
    sourceRef.current = source;
    activeRangeRef.current = { ...range, segmentId };
    anchorAudioTimeRef.current = safeOffset;
    anchorContextTimeRef.current = context.currentTime;
    publishCurrentTime(safeOffset);
    isPlayingRef.current = true;
    setIsPlaying(true);

    source.onended = () => {
      if (sourceRef.current !== source) return;
      sourceRef.current = null;
      source.disconnect();
      cancelAnimation();
      isPlayingRef.current = false;
      setIsPlaying(false);
      publishCurrentTime(range.end);
      if (segmentId) onRangeEndRef.current(segmentId);
    };

    // AudioBuffer offsets refer to decoded PCM time, so playback and the
    // waveform now share one sample-accurate timeline in every browser.
    source.start(0, safeOffset, range.end - safeOffset);
    animate();
  }, [animate, cancelAnimation, detachSource, publishCurrentTime]);

  const pause = useCallback(() => {
    requestNumberRef.current += 1;
    const position = exactCurrentTime();
    cancelAnimation();
    detachSource();
    isPlayingRef.current = false;
    setIsPlaying(false);
    publishCurrentTime(position);
  }, [cancelAnimation, detachSource, exactCurrentTime, publishCurrentTime]);

  const setPosition = useCallback((value: number) => {
    requestNumberRef.current += 1;
    cancelAnimation();
    detachSource();
    activeRangeRef.current = null;
    isPlayingRef.current = false;
    setIsPlaying(false);
    publishCurrentTime(clampAudioPosition(value, bufferRef.current?.duration));
  }, [cancelAnimation, detachSource, publishCurrentTime]);

  const seek = useCallback((value: number) => {
    const range = activeRangeRef.current;
    const nextTime = range
      ? Math.min(range.end, Math.max(range.start, value))
      : clampAudioPosition(value, bufferRef.current?.duration);
    if (isPlayingRef.current && range) {
      return playRange({ ...range, offset: nextTime });
    }
    publishCurrentTime(nextTime);
    return Promise.resolve();
  }, [playRange, publishCurrentTime]);

  return {
    audioBuffer,
    loadedAudioId,
    loadedAudioUrl,
    currentTime,
    isPlaying,
    loadFailed,
    pause,
    playRange,
    seek,
    setPosition,
  };
}
