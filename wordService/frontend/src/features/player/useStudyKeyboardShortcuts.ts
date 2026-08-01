import { useEffect } from "react";

interface UseStudyKeyboardShortcutsOptions {
  onBlurToggle: () => void;
  onMoveClip: (offset: -1 | 1) => void;
  onReplay: () => void;
  onSetSettingsOpen: (open: boolean) => void;
  onToggleMark: (key: "known" | "flagged") => void | Promise<void>;
  onTogglePlayback: () => void;
  settingsOpen: boolean;
}

export function useStudyKeyboardShortcuts({
  onBlurToggle,
  onMoveClip,
  onReplay,
  onSetSettingsOpen,
  onToggleMark,
  onTogglePlayback,
  settingsOpen,
}: UseStudyKeyboardShortcutsOptions) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const targetElement = event.target;
      const isWaveformInput = targetElement instanceof HTMLElement && !!targetElement.closest(".line-waveform input");
      if (!isWaveformInput && targetElement instanceof HTMLElement && targetElement.closest("input, select, textarea, [contenteditable='true']")) return;
      if (event.repeat) return;
      const key = event.key.toLowerCase();
      if (event.code === "Space") {
        event.preventDefault();
        onTogglePlayback();
      } else if (event.key === "ArrowRight" || key === "d") {
        event.preventDefault();
        onMoveClip(1);
      } else if (event.key === "ArrowLeft" || key === "a") {
        event.preventDefault();
        onMoveClip(-1);
      } else if (key === "r") {
        event.preventDefault();
        onReplay();
      } else if (key === "b") {
        event.preventDefault();
        onBlurToggle();
      } else if (key === "f") {
        event.preventDefault();
        void onToggleMark("flagged");
      } else if (key === "k" || event.key === "Enter") {
        event.preventDefault();
        void onToggleMark("known");
      } else if (event.key === "Escape" && settingsOpen) {
        onSetSettingsOpen(false);
      }
    };
    document.addEventListener("keydown", onKey, {capture: true});
    return () => document.removeEventListener("keydown", onKey, {capture: true});
  }, [onBlurToggle, onMoveClip, onReplay, onSetSettingsOpen, onToggleMark, onTogglePlayback, settingsOpen]);
}
