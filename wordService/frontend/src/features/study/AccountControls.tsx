import {useState, type FormEvent} from "react";

import { useI18n } from "../../i18n";
import type {useStudyState} from "./useStudyState";

export type AccountState = ReturnType<typeof useStudyState>;

export function AccountControls({state}: {state: AccountState}) {
  const {copy, localizeMessage} = useI18n();
  const [authOpen, setAuthOpen] = useState(false);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setBusy(true);
    try { await state[mode](email, password); setAuthOpen(false); setPassword(""); } catch { /* shown by the hook */ } finally { setBusy(false); }
  };

  const logout = async () => {
    await state.logout();
    setAuthOpen(false);
    setPassword("");
  };

  return <section className="account-settings" aria-labelledby="account-settings-title">
    <div className="account-settings-heading">
      <div>
        <span className="eyebrow">{copy.account.eyebrow}</span>
        <h3 id="account-settings-title">{copy.account.title}</h3>
      </div>
      <span className="account-settings-state">{state.session ? copy.account.signedInAs : copy.account.notSignedIn}</span>
    </div>
    {state.session
      ? <div className="account-settings-session"><span className="account-settings-email">{state.session.user.email}</span><button type="button" onClick={() => void logout()}>{copy.account.logOut}</button></div>
      : authOpen
        ? <form className="account-settings-form" onSubmit={event => void submit(event)}>
          <p>{copy.account.progressStored}</p>
          <label>{copy.account.email}<input type="email" required value={email} onChange={event => setEmail(event.target.value)} /></label>
          <label>{copy.account.password}<input type="password" minLength={8} required value={password} onChange={event => setPassword(event.target.value)} /></label>
          <div className="account-settings-actions">
            <button type="submit" disabled={busy}>{busy ? copy.account.working : mode === "login" ? copy.account.signIn : copy.account.register}</button>
            <button type="button" onClick={() => setAuthOpen(false)}>{copy.account.cancel}</button>
          </div>
          {state.accountError ? <p role="alert">{localizeMessage(state.accountError)}</p> : null}
          <button type="button" className="account-settings-link" onClick={() => setMode(value => value === "login" ? "register" : "login")}>{mode === "login" ? copy.account.needAccount : copy.account.alreadyRegistered}</button>
        </form>
        : <button type="button" onClick={() => setAuthOpen(true)}>{copy.account.signInOrRegister}</button>}
  </section>;
}

export function AccountImportDialog({state}: {state: AccountState}) {
  const {copy, localizeMessage} = useI18n();
  const [busy, setBusy] = useState(false);
  if (!state.pendingImport) return null;

  return <div className="react-modal-backdrop account-import-backdrop"><section className="account-modal" role="dialog" aria-modal="true" aria-labelledby="import-title">
      <h2 id="import-title">{copy.account.guestProgressFound}</h2>
      <p>{copy.account.chooseProgress(state.pendingImport.account.user.email)}</p>
      {state.accountError ? <p role="alert">{localizeMessage(state.accountError)}</p> : null}
      <button type="button" disabled={busy} onClick={() => { setBusy(true); void state.importGuest().catch(() => undefined).finally(() => setBusy(false)); }}>{copy.account.importGuestProgress}</button>
      <button type="button" disabled={busy} onClick={state.keepAccount}>{copy.account.keepAccountProgress}</button>
      <button type="button" disabled={busy} onClick={() => { setBusy(true); void state.cancelImport().catch(() => undefined).finally(() => setBusy(false)); }}>{copy.account.cancelImport}</button>
    </section></div>;
}
