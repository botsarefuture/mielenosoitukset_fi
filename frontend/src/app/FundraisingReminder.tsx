import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { confirmReminder, readReminderLink, reminderCopy as c, removeReminder, signUpForReminder } from './fundraising-reminder';
import type { ReminderMode } from './fundraising-reminder';

type Outcome = { kind: 'ok' | 'error'; text: string } | null;

/** Signup form for the one opening reminder. Rendered only while the Go API reports it enabled. */
export function ReminderSignup({ privacyUrl }: { privacyUrl: string }) {
  const [sending, setSending] = useState(false);
  const [outcome, setOutcome] = useState<Outcome>(null);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setSending(true);
    setOutcome(null);
    const result = await signUpForReminder({
      email: String(form.get('email') ?? ''), resultsConsent: form.get('results') === 'on', website: String(form.get('hp_trap') ?? ''),
    });
    setSending(false);
    if (result.ok) {
      setOutcome({ kind: 'ok', text: result.message || c.intro });
      (event.target as HTMLFormElement).reset();
    } else {
      setOutcome({ kind: 'error', text: result.status === 429 ? c.rateLimited : result.message || c.error });
    }
  };
  return <section className="fundraising-reminder" aria-labelledby="reminder-title">
    <h3 id="reminder-title">{c.title}</h3>
    <p>{c.intro}</p>
    <form className="fundraising-reminder__form" onSubmit={submit}>
      <div hidden aria-hidden="true">
        <label htmlFor="reminder-hp">Jätä tämä kenttä tyhjäksi</label>
        <input type="text" id="reminder-hp" name="hp_trap" tabIndex={-1} autoComplete="off" />
      </div>
      <label htmlFor="reminder-email">{c.emailLabel}</label>
      <input type="email" id="reminder-email" name="email" required maxLength={254} autoComplete="email" inputMode="email" />
      <label className="fundraising-reminder__check">
        <input type="checkbox" name="consent" required />
        <span>{c.consent}</span>
      </label>
      <label className="fundraising-reminder__check">
        <input type="checkbox" name="results" />
        <span>{c.results}<small>{c.resultsHint}</small></span>
      </label>
      <button type="submit" className="fundraising-calendar" disabled={sending}>{sending ? c.sending : c.submit}</button>
    </form>
    <p className={`fundraising-reminder__status${outcome?.kind === 'error' ? ' fundraising-reminder__status--error' : ''}`} role="status">{outcome?.text ?? ''}</p>
    <p className="fundraising-prelaunch__note">{c.retention} <a href={privacyUrl}>{c.privacy}</a>.</p>
  </section>;
}

/** The page behind the links in the reminder mails: confirm the signup, or delete the address. */
export function ReminderLinkPanel() {
  const [link, setLink] = useState<{ mode: ReminderMode; token: string } | null>(null);
  const [state, setState] = useState<'idle' | 'working' | 'done'>('idle');
  const [outcome, setOutcome] = useState<Outcome>(null);
  useEffect(() => { setLink(readReminderLink(window.location.search, window.location.hash)); }, []);
  if (!link) return null;
  const confirming = link.mode === 'vahvista';
  const act = async () => {
    setState('working');
    const result = await (confirming ? confirmReminder : removeReminder)(link.token);
    if (result.ok) {
      setState('done');
      setOutcome({ kind: 'ok', text: confirming ? c.confirmed : c.removed });
    } else {
      setState('idle');
      setOutcome({ kind: 'error', text: result.status === 410 || !link.token ? result.message || c.badLink : result.message || c.error });
    }
  };
  return <section className="public-content__card fundraising-reminder-link" aria-labelledby="reminder-link-title">
    <h2 id="reminder-link-title">{confirming ? c.confirmTitle : c.removeTitle}</h2>
    {state !== 'done' && <>
      <p>{confirming ? c.confirmIntro : c.removeIntro}</p>
      <button type="button" className="fundraising-calendar" onClick={act} disabled={state === 'working' || !link.token}>{confirming ? c.confirmButton : c.removeButton}</button>
    </>}
    <p className={`fundraising-reminder__status${outcome?.kind === 'error' ? ' fundraising-reminder__status--error' : ''}`} role="status">
      {outcome?.text ?? (link.token ? '' : c.badLink)}
    </p>
  </section>;
}
