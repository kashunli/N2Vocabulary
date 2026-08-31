import { useMemo, useRef, useState } from "react";

import { useI18n } from "../../i18n";
import type { Entry } from "../../types";
import { createMarkedWordsExport, parseMarkedWordsExport } from "./markedWords.mjs";
import type { ImportedMark, StudySnapshot, StudyStateStore } from "./studyStateTypes";

interface MarkedWordsControlsProps {
  entries: Entry[];
  snapshot: StudySnapshot;
  store: StudyStateStore;
}

function filenameDate() {
  return new Date().toISOString().slice(0, 10);
}

function isInvalidFileError(error: unknown) {
  return error instanceof Error && error.message.startsWith("Invalid marked words file:");
}

export function MarkedWordsControls({entries, snapshot, store}: MarkedWordsControlsProps) {
  const {copy} = useI18n();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");
  const markedCount = useMemo(
    () => Object.values(snapshot.cards).filter((card) => card.status === "known" || card.status === "flagged").length,
    [snapshot.cards],
  );

  const exportMarkedWords = () => {
    try {
      const payload = createMarkedWordsExport(snapshot, entries);
      const blob = new Blob([JSON.stringify(payload, null, 2)], {type: "application/json"});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `n2-marked-words-${filenameDate()}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
      setFeedback(copy.settings.markedWordsExported(payload.items.length));
    } catch {
      setFeedback(copy.errors.exportMarkedWords);
    }
  };

  const chooseImportFile = () => {
    setFeedback("");
    fileInputRef.current?.click();
  };

  const importMarkedWords = async (file: File) => {
    setBusy(true);
    setFeedback("");
    try {
      let fileValue: unknown;
      try {
        fileValue = JSON.parse(await file.text());
      } catch {
        throw new Error("Invalid marked words file: invalid JSON");
      }
      const parsed = parseMarkedWordsExport(fileValue) as {
        items: ImportedMark[];
      };
      await store.importMarks(parsed.items);
      setFeedback(copy.settings.markedWordsImported(parsed.items.length));
    } catch (error: unknown) {
      setFeedback(isInvalidFileError(error) ? copy.errors.invalidMarkedWordsFile : copy.errors.importMarkedWords);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="react-marked-words" aria-labelledby="react-marked-words-title">
      <div className="react-setting-copy">
        <span id="react-marked-words-title">{copy.settings.markedWords}</span>
        <output>{copy.settings.markedWordsCount(markedCount)}</output>
        <p>{copy.settings.markedWordsDescription}</p>
      </div>
      <div className="react-setting-options react-marked-words-actions" role="group" aria-label={copy.settings.markedWords}>
        <button type="button" onClick={exportMarkedWords} disabled={busy}>{copy.settings.exportMarkedWords}</button>
        <button type="button" onClick={chooseImportFile} disabled={busy}>{copy.settings.importMarkedWords}</button>
      </div>
      <input
        ref={fileInputRef}
        className="react-marked-words-file"
        type="file"
        accept="application/json,.json"
        aria-label={copy.settings.chooseMarkedWordsFile}
        onChange={(event) => {
          const file = event.currentTarget.files?.[0];
          event.currentTarget.value = "";
          if (file) void importMarkedWords(file);
        }}
      />
      {feedback ? <p className="react-marked-words-feedback" role="status" aria-live="polite">{feedback}</p> : null}
    </section>
  );
}
