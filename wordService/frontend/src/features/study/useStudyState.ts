import {useEffect, useMemo, useState} from "react";

import {getLegacyMarkSeed} from "../../api";
import {LocalStudyStateStore} from "./localStudyState.mjs";
import type {StudySnapshot, StudyStateStore} from "./studyStateTypes";

export function useStudyState() {
  const store = useMemo(() => new LocalStudyStateStore() as StudyStateStore, []);
  const [snapshot, setSnapshot] = useState<StudySnapshot>(() => store.load());
  const [ready, setReady] = useState(false);

  useEffect(() => store.subscribe(setSnapshot), [store]);

  useEffect(() => {
    let cancelled = false;
    getLegacyMarkSeed()
      .then(payload => {
        if (!cancelled) store.seedLegacy(payload.items);
      })
      .catch(error => console.warn("Could not import legacy study marks", error))
      .finally(() => { if (!cancelled) setReady(true); });
    return () => { cancelled = true; };
  }, [store]);

  return {store, snapshot, ready, dueCount: store.dueCards().length};
}
