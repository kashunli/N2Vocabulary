import {useState} from "react";

import { useI18n } from "../../i18n";
import type {useStudyState} from "./useStudyState";

type AccountState = ReturnType<typeof useStudyState>;

export function AccountControls({state}: {state: AccountState}) {
  const {copy, localizeMessage} = useI18n();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true);
    try { await state[mode](email, password); setOpen(false); setPassword(""); } catch { /* shown by the hook */ } finally { setBusy(false); }
  };

  return <>
    <div className="account-corner">
      {state.session && !state.pendingImport
        ? <><span>{state.session.user.email}</span><button type="button" onClick={() => void state.logout()}>{copy.account.logOut}</button></>
        : <button type="button" onClick={() => setOpen(true)}>{copy.account.signInOrRegister}</button>}
    </div>
    {open && !state.pendingImport ? <div className="react-modal-backdrop"><section className="account-modal" role="dialog" aria-modal="true" aria-labelledby="account-title">
      <h2 id="account-title">{mode === "login" ? copy.account.signIn : copy.account.createAccount}</h2>
      <p>{copy.account.progressStored}</p>
      <form onSubmit={event => void submit(event)}><label>{copy.account.email}<input type="email" required value={email} onChange={event => setEmail(event.target.value)} /></label><label>{copy.account.password}<input type="password" minLength={8} required value={password} onChange={event => setPassword(event.target.value)} /></label><button disabled={busy}>{busy ? copy.account.working : mode === "login" ? copy.account.signIn : copy.account.register}</button></form>
      {state.accountError ? <p role="alert">{localizeMessage(state.accountError)}</p> : null}
      <button type="button" onClick={() => setMode(value => value === "login" ? "register" : "login")}>{mode === "login" ? copy.account.needAccount : copy.account.alreadyRegistered}</button>
      <button type="button" onClick={() => setOpen(false)}>{copy.account.cancel}</button>
    </section></div> : null}
    {state.pendingImport ? <div className="react-modal-backdrop"><section className="account-modal" role="dialog" aria-modal="true" aria-labelledby="import-title">
      <h2 id="import-title">{copy.account.guestProgressFound}</h2>
      <p>{copy.account.chooseProgress(state.pendingImport.account.user.email)}</p>
      {state.accountError ? <p role="alert">{localizeMessage(state.accountError)}</p> : null}
      <button type="button" disabled={busy} onClick={() => { setBusy(true); void state.importGuest().catch(() => undefined).finally(() => setBusy(false)); }}>{copy.account.importGuestProgress}</button>
      <button type="button" disabled={busy} onClick={state.keepAccount}>{copy.account.keepAccountProgress}</button>
      <button type="button" disabled={busy} onClick={() => void state.cancelImport()}>{copy.account.cancelImport}</button>
    </section></div> : null}
  </>;
}
