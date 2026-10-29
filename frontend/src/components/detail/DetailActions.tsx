import { startTransition, useActionState, useEffect, useId, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import type { DetailEvent, DetailProps } from './types';
import { accountEndpoint, accountRequest, actionMessage } from './account';
import { safeHref } from './content';

type Feedback = { ok: boolean; message: string } | null;
export type DialogKind = 'reminder' | 'report' | 'invite';
function FeedbackMessage({ value }: { value: Feedback }) {
  return value ? <p className={`detail-feedback${value.ok ? ' is-success' : ' is-error'}`} role={value.ok ? 'status' : 'alert'}>{value.message}</p> : null;
}
function Dialog({ title, close, label, children }: { title: string; close(): void; label: string; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  const heading = useId();
  useEffect(() => {
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    ref.current?.showModal();
    return () => { ref.current?.close(); if (trigger?.isConnected) trigger.focus({ preventScroll: true }); };
  }, []);
  return <dialog ref={ref} className="detail-action-dialog" aria-labelledby={heading} onCancel={() => close()}>
    <header><h2 id={heading}>{title}</h2><button type="button" className="detail-button detail-button--quiet" onClick={close}>{label}</button></header>{children}
  </dialog>;
}
function ReminderForm({ event, props }: { event: DetailEvent; props: DetailProps }) {
  const [email, setEmail] = useState('');
  const id = useId();
  const [result, submit, pending] = useActionState<Feedback, FormData>(async (_previous, form) => {
    try {
      const payload = await accountRequest(accountEndpoint(props.urls.reminder, event._id), { method: 'POST', body: form }, props.csrfToken);
      if (payload.status !== 'OK') return { ok: false, message: typeof payload.message === 'string' ? payload.message : props.messages.actionError };
      return { ok: true, message: typeof payload.message === 'string' ? payload.message : props.messages.saved };
    } catch (error) { return { ok: false, message: actionMessage(error, props.messages.actionError) }; }
  }, null);
  return <>{!result?.ok && <form action={submit} className="detail-form" aria-busy={pending}>
    <label htmlFor={id}>{props.messages.email}</label><input id={id} type="email" name="user_email" value={email} onChange={e => setEmail(e.target.value)} autoComplete="email" required autoFocus disabled={pending} />
    <button className="detail-button detail-button--primary" type="submit" disabled={pending}>{pending ? props.messages.sending : props.messages.reminder}</button>
  </form>}<FeedbackMessage value={result} /></>;
}
function ReportForm({ event, props }: { event: DetailEvent; props: DetailProps }) {
  const [description, setDescription] = useState('');
  const [email, setEmail] = useState('');
  const [cancelled, setCancelled] = useState(false);
  const id = useId();
  const [result, submit, pending] = useActionState<Feedback, FormData>(async (_previous, form) => {
    form.set('type', 'demonstration'); form.set('demo_id', event._id);
    try {
      const payload = await accountRequest(accountEndpoint(props.urls.report, event._id), { method: 'POST', body: form }, props.csrfToken);
      if (payload.status !== 'OK') return { ok: false, message: typeof payload.message === 'string' ? payload.message : props.messages.actionError };
      return { ok: true, message: typeof payload.message === 'string' ? payload.message : props.messages.saved };
    } catch (error) { return { ok: false, message: actionMessage(error, props.messages.actionError) }; }
  }, null);
  return <>{!result?.ok && <form action={submit} className="detail-form" aria-busy={pending}>
    <label htmlFor={`${id}-description`}>{props.messages.reportDescription}</label><textarea id={`${id}-description`} name="error" value={description} onChange={e => setDescription(e.target.value)} required maxLength={5000} rows={5} autoFocus disabled={pending} />
    <label className="detail-checkbox"><input type="checkbox" name="mark_cancelled" value="1" checked={cancelled} onChange={e => setCancelled(e.target.checked)} disabled={pending} />{props.messages.markCancelled}</label>
    <label htmlFor={`${id}-email`}>{props.messages.emailOptional}</label><input id={`${id}-email`} type="email" name="reporter_email" value={email} onChange={e => setEmail(e.target.value)} autoComplete="email" disabled={pending} />
    <button className="detail-button detail-button--primary" type="submit" disabled={pending || !description.trim()}>{pending ? props.messages.sending : props.messages.sendReport}</button>
  </form>}<FeedbackMessage value={result} /></>;
}
type Friend = { id: string; name: string };
function InviteForm({ event, props }: { event: DetailEvent; props: DetailProps }) {
  const [friends, setFriends] = useState<Friend[] | null>(null);
  const [error, setError] = useState(false);
  const [revision, reload] = useState(0);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  useEffect(() => {
    const controller = new AbortController(); let active = true;
    setFriends(null); setError(false);
    const timeout = window.setTimeout(() => controller.abort(), 10_000);
    accountRequest(accountEndpoint(props.urls.friends, event._id), { signal: controller.signal }, props.csrfToken).then(data => {
      if (!active || !Array.isArray(data.friends)) throw new Error('Invalid friends');
      const unique = new Map<string, Friend>();
      for (const raw of data.friends) {
        if (!raw || typeof raw !== 'object' || typeof raw._id !== 'string' || !/^[a-f\d]{24}$/i.test(raw._id)) continue;
        unique.set(raw._id, { id: raw._id, name: typeof raw.displayname === 'string' ? raw.displayname : typeof raw.username === 'string' ? raw.username : raw._id });
      }
      setFriends([...unique.values()]);
    }).catch(() => { if (active) setError(true); }).finally(() => window.clearTimeout(timeout));
    return () => { active = false; controller.abort(); window.clearTimeout(timeout); };
  }, [event._id, props.urls.friends, props.csrfToken, revision]);
  const [result, submit, pending] = useActionState<Feedback, FormData>(async (_previous, form) => {
    const allowed = new Set(friends?.map(friend => friend.id));
    const selected = [...new Set(form.getAll('friend_ids').filter((value): value is string => typeof value === 'string' && allowed.has(value)))];
    if (!selected.length) return { ok: false, message: props.messages.chooseFriends };
    try {
      const payload = await accountRequest(accountEndpoint(props.urls.invite, event._id), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ friend_ids: selected }) }, props.csrfToken);
      if (!Array.isArray(payload.invited_friends)) return { ok: false, message: props.messages.actionError };
      return { ok: true, message: props.messages.inviteSent };
    } catch (error) { return { ok: false, message: actionMessage(error, props.messages.actionError) }; }
  }, null);
  if (error) return <div role="alert"><p>{props.messages.friendsError}</p><button className="detail-button" onClick={() => reload(value => value + 1)}>{props.messages.retry}</button></div>;
  if (!friends) return <p role="status">{props.messages.loading}</p>;
  if (!friends.length) return <p>{props.messages.noFriends}</p>;
  return <>{!result?.ok && <form action={submit} className="detail-form" aria-busy={pending}><div className="detail-friend-list">{friends.map(friend => <label className="detail-checkbox" key={friend.id}><input name="friend_ids" type="checkbox" value={friend.id} checked={selectedIds.includes(friend.id)} onChange={event => setSelectedIds(current => event.target.checked ? [...current, friend.id] : current.filter(id => id !== friend.id))} disabled={pending} />{friend.name}</label>)}</div>
    <button className="detail-button detail-button--primary" type="submit" disabled={pending}>{pending ? props.messages.sending : props.messages.sendInvites}</button>
  </form>}<FeedbackMessage value={result} /></>;
}
export function DetailActionDialog({ kind, event, props, close }: { kind: DialogKind; event: DetailEvent; props: DetailProps; close(): void }) {
  const title = kind === 'reminder' ? props.messages.reminder : kind === 'report' ? props.messages.report : props.messages.invite;
  return <Dialog title={title} label={props.messages.close} close={close}>{kind === 'reminder' ? <ReminderForm event={event} props={props} /> : kind === 'report' ? <ReportForm event={event} props={props} />
    : props.authenticated ? <InviteForm event={event} props={props} /> : <><p>{props.messages.loginRequired}</p><a className="detail-button detail-button--primary" href={safeHref(props.urls.loginInvite ?? props.urls.login)}>{props.messages.login}</a></>}</Dialog>;
}

export function Participation({ event, props }: { event: DetailEvent; props: DetailProps }) {
  const [attending, setAttending] = useState<boolean | null>(null);
  const [readError, setReadError] = useState(false);
  const [revision, reload] = useState(0);
  const intentUsed = useRef(false);
  useEffect(() => {
    if (!props.authenticated) return;
    const controller = new AbortController(); let active = true;
    setAttending(null); setReadError(false);
    accountRequest(accountEndpoint(props.urls.attendance, event._id), { signal: controller.signal }, props.csrfToken).then(payload => {
      if (typeof payload.attending !== 'boolean') throw new Error('Invalid attendance');
      if (active) setAttending(payload.attending);
    }).catch(() => { if (active) setReadError(true); });
    return () => { active = false; controller.abort(); };
  }, [event._id, props.authenticated, props.urls.attendance, props.csrfToken, revision]);
  const [result, toggle, pending] = useActionState<Feedback, FormData>(async () => {
    if (attending === null) return { ok: false, message: props.messages.actionError };
    try {
      const payload = await accountRequest(accountEndpoint(attending ? props.urls.unlike : props.urls.like, event._id), { method: 'POST' }, props.csrfToken);
      if (typeof payload.likes !== 'number') throw new Error('Invalid attendance');
      setAttending(!attending); return null;
    } catch { reload(value => value + 1); return { ok: false, message: props.messages.actionError }; }
  }, null);
  useEffect(() => {
    if (!props.authenticated || props.initialAction !== 'attend' || attending === null || intentUsed.current) return;
    intentUsed.current = true; props.onIntentConsumed?.();
    if (!attending) startTransition(() => toggle(new FormData()));
  }, [props.authenticated, props.initialAction, attending, props.onIntentConsumed, toggle]);
  if (!props.authenticated) return <><p className="detail-note">{props.messages.loginRequired}</p><a className="detail-button" href={safeHref(props.urls.login)}>{props.messages.login}</a></>;
  if (readError) return <><p role="alert">{props.messages.actionError}</p><button className="detail-button" type="button" onClick={() => reload(value => value + 1)}>{props.messages.retry}</button></>;
  return <><form action={toggle} aria-busy={pending || attending === null}><button className={`detail-button${attending ? '' : ' detail-button--primary'}`} type="submit" disabled={pending || attending === null} aria-pressed={attending ?? false}>{attending === null ? props.messages.loading : attending ? props.messages.cancelAttendance : props.messages.attend}</button></form><FeedbackMessage value={result} /></>;
}
