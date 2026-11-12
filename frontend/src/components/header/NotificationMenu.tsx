import { useCallback, useEffect, useRef, useState } from 'react';
import type { HeaderProps } from './types';
import { Icon } from './NavigationLink';

type Notice = { id: string; type: string; link: string; message: string; time: string; read: boolean };
const icons: Record<string, string> = {
  org_invite: 'fa-building-circle-check', friend_request: 'fa-user-plus', demo_invite: 'fa-bullhorn',
  demo_cancelled: 'fa-ban', recurring_demo_update: 'fa-arrows-rotate',
};
export function safeNotificationHref(value: string) {
  if (value === '#') return '#';
  try {
    const url = new URL(value, window.location.origin);
    return url.origin === window.location.origin ? `${url.pathname}${url.search}${url.hash}` : '#';
  } catch { return '#'; }
}
function timestamp(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(document.documentElement.lang || 'fi', {
    dateStyle: 'medium', timeStyle: 'short',
  }).format(date);
}
export function NotificationMenu({ notifications: urls, messages, path }: Pick<HeaderProps, 'notifications' | 'messages' | 'path'>) {
  const [open, setOpen] = useState(false);
  const [notices, setNotices] = useState<Notice[]>([]);
  const [unread, setUnread] = useState(urls.unread);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [marking, setMarking] = useState(false);
  const [markError, setMarkError] = useState(false);
  const wrap = useRef<HTMLLIElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const pending = useRef<AbortController | null>(null);
  const load = useCallback(async (showLoading = false) => {
    pending.current?.abort();
    const controller = new AbortController(); pending.current = controller;
    if (showLoading) setState('loading');
    try {
      const response = await fetch(urls.list, { credentials: 'same-origin', headers: { Accept: 'application/json' }, signal: controller.signal });
      if (!response.ok) throw new Error('Notification request failed');
      const data: unknown = await response.json();
      if (!Array.isArray(data) || !data.every(item => item && typeof item === 'object'
        && typeof item.message === 'string' && typeof item.link === 'string' && typeof item.time === 'string')) {
        throw new Error('Invalid notifications');
      }
      if (controller.signal.aborted) return;
      setNotices(data); setUnread(data.filter(item => !item.read).length); setState('ready');
    } catch {
      if (!controller.signal.aborted) setState('error');
    }
  }, [urls.list]);
  useEffect(() => {
    const interval = window.setInterval(() => void load(), 60_000);
    return () => { window.clearInterval(interval); pending.current?.abort(); };
  }, [load]);
  useEffect(() => {
    function outside(event: Event) { if (!wrap.current?.contains(event.target as Node)) setOpen(false); }
    document.addEventListener('pointerdown', outside);
    document.addEventListener('focusin', outside);
    return () => {
      document.removeEventListener('pointerdown', outside); document.removeEventListener('focusin', outside);
    };
  }, []);
  async function markRead() {
    if (marking) return;
    setMarking(true); setMarkError(false);
    try {
      const response = await fetch(urls.markRead, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error('Mark read failed');
      await load();
    } catch { setMarkError(true); }
    finally { setMarking(false); }
  }
  return <li id="notif-wrap" className="position-relative d-flex align-items-center ms-2" ref={wrap} aria-expanded={open}
    onKeyDown={event => {
      if (event.key === 'Escape' && open) { event.stopPropagation(); setOpen(false); button.current?.focus(); }
    }}>
    <button id="notif-btn" className="btn p-0 position-relative" type="button" ref={button}
      aria-label={messages.notifications} aria-haspopup="dialog" aria-controls="notif-panel" aria-expanded={open}
      onClick={() => { setOpen(!open); if (!open) { setMarkError(false); void load(true); } }}>
      <i className="fa-solid fa-bell fs-5" aria-hidden="true" />
      {unread > 0 && <span className="notif-badge position-absolute top-0 start-100 translate-middle">{unread > 99 ? '99+' : unread}</span>}
    </button>
    <div id="notif-panel" className="notif-panel card shadow border-0" role="dialog" aria-labelledby="notif-panel-title" aria-hidden={!open}>
      <div className="card-header d-flex justify-content-between align-items-center py-2 px-3 border-0">
        <span className="fw-semibold" id="notif-panel-title">{messages.notifications}</span>
        <button id="mark-read-btn" type="button" className={`btn btn-link btn-sm text-decoration-none${unread ? '' : ' d-none'}`}
          disabled={marking} onClick={() => void markRead()}>{messages.markRead}</button>
      </div>
      <div className="list-group list-group-flush" id="notif-list" aria-live="polite" aria-busy={state === 'loading'}>
        {markError ? <div className="notif-state notif-state--error" role="alert">{messages.markError}</div> : state !== 'ready' || !notices.length ? <div className={`notif-state notif-state--${state === 'ready' ? 'empty' : state}`}
          role={state === 'error' ? 'alert' : 'status'}>
          {state === 'loading' && <Icon name="fa-spinner fa-spin" />}
          <span>{state === 'loading' ? messages.loading : state === 'error' ? messages.loadError : messages.empty}</span>
        </div> : notices.map((notice, index) => <div key={notice.id || index} className={`notif-item${notice.read ? '' : ' is-unread'}`}>
          <a className="notif-item__link" href={safeNotificationHref(notice.link)}>
            <span className="notif-item__icon"><Icon name={icons[notice.type] || 'fa-circle-info'} /></span>
            <span className="notif-item__content"><span className="notif-item__message">{notice.message}</span>
              <time className="notif-item__time" dateTime={notice.time}>{timestamp(notice.time)}</time></span>
          </a>
        </div>)}
      </div>
      <div className="card-footer text-center py-2"><a href={urls.all} className={`small${path === urls.all ? ' d-none' : ''}`}>{messages.all}</a></div>
    </div>
  </li>;
}
