import {useState} from "react";
import type {useStudyState} from "./useStudyState";

type AccountState = ReturnType<typeof useStudyState>;

export function AccountControls({state}: {state: AccountState}) {
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
        ? <><span>{state.session.user.email}</span><button type="button" onClick={() => void state.logout()}>Log out</button></>
        : <button type="button" onClick={() => setOpen(true)}>Sign in / Register</button>}
    </div>
    {open && !state.pendingImport ? <div className="react-modal-backdrop"><section className="account-modal" role="dialog" aria-modal="true" aria-labelledby="account-title">
      <h2 id="account-title">{mode === "login" ? "Sign in" : "Create account"}</h2>
      <p>Account progress is stored in the separate local users database.</p>
      <form onSubmit={event => void submit(event)}><label>Email<input type="email" required value={email} onChange={event => setEmail(event.target.value)} /></label><label>Password<input type="password" minLength={8} required value={password} onChange={event => setPassword(event.target.value)} /></label><button disabled={busy}>{busy ? "Working…" : mode === "login" ? "Sign in" : "Register"}</button></form>
      {state.accountError ? <p role="alert">{state.accountError}</p> : null}
      <button type="button" onClick={() => setMode(value => value === "login" ? "register" : "login")}>{mode === "login" ? "Need an account? Register" : "Already registered? Sign in"}</button>
      <button type="button" onClick={() => setOpen(false)}>Cancel</button>
    </section></div> : null}
    {state.pendingImport ? <div className="react-modal-backdrop"><section className="account-modal" role="dialog" aria-modal="true" aria-labelledby="import-title">
      <h2 id="import-title">Guest progress found</h2>
      <p>Choose which progress should become active for {state.pendingImport.account.user.email}. Study changes are paused until you decide.</p>
      {state.accountError ? <p role="alert">{state.accountError}</p> : null}
      <button type="button" disabled={busy} onClick={() => { setBusy(true); void state.importGuest().catch(() => undefined).finally(() => setBusy(false)); }}>Import guest progress</button>
      <button type="button" disabled={busy} onClick={state.keepAccount}>Keep account progress</button>
      <button type="button" disabled={busy} onClick={() => void state.cancelImport()}>Cancel and remain logged out</button>
    </section></div> : null}
  </>;
}
