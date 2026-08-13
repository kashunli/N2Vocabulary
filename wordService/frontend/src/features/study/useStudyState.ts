import {useCallback, useEffect, useMemo, useState} from "react";

import {getAccountStudyState, getCurrentUser, getLegacyMarkSeed, importGuestStudyState, loginAccount, logoutAccount, registerAccount, type AuthSession} from "../../api";
import {AccountStudyStateStore} from "./AccountStudyStateStore";
import {LocalStudyStateStore} from "./localStudyState.mjs";
import type {StudySnapshot, StudyStateStore} from "./studyStateTypes";

export type ImportDecision = {account: AuthSession; accountSnapshot: StudySnapshot; guestChecksum: string};

async function checksum(snapshot: StudySnapshot) {
  const bytes = new TextEncoder().encode(JSON.stringify(snapshot));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
}

export function useStudyState() {
  const localStore = useMemo(() => new LocalStudyStateStore(), []);
  const [store, setStore] = useState<StudyStateStore>(localStore as StudyStateStore);
  const [snapshot, setSnapshot] = useState<StudySnapshot>(() => store.load());
  const [session, setSession] = useState<AuthSession>();
  const [pendingImport, setPendingImport] = useState<ImportDecision>();
  const [ready, setReady] = useState(false);
  const [accountError, setAccountError] = useState("");

  const activateAccount = useCallback((account: AuthSession, accountSnapshot: StudySnapshot) => {
    const next = new AccountStudyStateStore(account.csrf_token, accountSnapshot);
    setSession(account); setStore(next); setSnapshot(accountSnapshot); setPendingImport(undefined); setAccountError("");
  }, []);

  const considerAccount = useCallback(async (account: AuthSession) => {
    const accountSnapshot = await getAccountStudyState();
    const guest = localStore.exportSnapshot() as StudySnapshot;
    if (!Object.keys(guest.cards).length) { activateAccount(account, accountSnapshot); return; }
    const guestChecksum = await checksum(guest);
    const dismissal = localStorage.getItem(`n2-word-service:guest-import-dismissed:${account.user.id}`);
    if (dismissal === guestChecksum) { activateAccount(account, accountSnapshot); return; }
    setSession(account); setPendingImport({account, accountSnapshot, guestChecksum});
  }, [activateAccount, localStore]);

  useEffect(() => store.subscribe(setSnapshot), [store]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const account = await getCurrentUser();
        if (!cancelled) await considerAccount(account);
      } catch {
        try {
          const payload = await getLegacyMarkSeed();
          if (!cancelled) localStore.seedLegacy(payload.items);
        } catch (error) { console.warn("Could not import legacy study marks", error); }
      } finally { if (!cancelled) setReady(true); }
    })();
    return () => { cancelled = true; };
  }, [considerAccount, localStore]);

  const authenticate = useCallback(async (mode: "login" | "register", email: string, password: string) => {
    setAccountError("");
    try {
      const account = mode === "login" ? await loginAccount(email, password) : await registerAccount(email, password);
      await considerAccount(account);
    } catch (error) { setAccountError(error instanceof Error ? error.message : "Account request failed."); throw error; }
  }, [considerAccount]);

  const logout = useCallback(async () => {
    if (session) await logoutAccount(session.csrf_token);
    setSession(undefined); setPendingImport(undefined); setStore(localStore as StudyStateStore); setSnapshot(localStore.load());
  }, [localStore, session]);

  const importGuest = useCallback(async () => {
    if (!pendingImport) return;
    const guest = localStore.exportSnapshot() as StudySnapshot;
    const importId = crypto.randomUUID();
    localStore.archiveSnapshot(importId, pendingImport.guestChecksum);
    try {
      const merged = await importGuestStudyState(pendingImport.account.csrf_token, {import_id: importId, snapshot_checksum: pendingImport.guestChecksum, cards: guest.cards});
      localStore.clearActive();
      activateAccount(pendingImport.account, merged);
    } catch (error) { setAccountError(error instanceof Error ? error.message : "Guest import failed."); throw error; }
  }, [activateAccount, localStore, pendingImport]);

  const keepAccount = useCallback(() => {
    if (!pendingImport) return;
    localStorage.setItem(`n2-word-service:guest-import-dismissed:${pendingImport.account.user.id}`, pendingImport.guestChecksum);
    activateAccount(pendingImport.account, pendingImport.accountSnapshot);
  }, [activateAccount, pendingImport]);

  const cancelImport = useCallback(async () => { await logout(); }, [logout]);

  return {store, snapshot, ready, dueCount: store.dueCards().length, session, pendingImport, accountError,
    login: (email: string, password: string) => authenticate("login", email, password),
    register: (email: string, password: string) => authenticate("register", email, password),
    logout, importGuest, keepAccount, cancelImport};
}
