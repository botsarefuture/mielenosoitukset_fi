import { useEffect, useRef, useState } from 'react';
import { clockLabel } from '../detail/content';
import type { Demonstration, Friend, ListingProps } from './types';

/** Server rendering has no location; the render entry supplies the public origin. */
function pageOrigin() {
  if (typeof window !== 'undefined') return window.location.origin;
  return (globalThis as { __MOSO_ORIGIN__?: string }).__MOSO_ORIGIN__ ?? '';
}
export function internalHref(value: string) {
  try {
    const url = new URL(value, pageOrigin());
    return url.origin === pageOrigin() ? `${url.pathname}${url.search}${url.hash}` : '#';
  } catch { return '#'; }
}
export function eventHref(event: Demonstration, props: Pick<ListingProps, 'seriesUrl' | 'detailUrl'>) {
  const fallback = event.parent ? props.seriesUrl.replace('__ID__', encodeURIComponent(event.parent))
    : props.detailUrl.replace('__ID__', encodeURIComponent(String(event.slug || event.running_number || event._id)));
  return internalHref(event.detail_url || fallback);
}
function inviteHref(href: string) {
  const url = new URL(href, pageOrigin());
  url.searchParams.set('action', 'inviteFriends');
  return `${url.pathname}${url.search}${url.hash}`;
}

export type CardProps = Pick<ListingProps, 'seriesUrl' | 'detailUrl' | 'tagUrl' | 'authenticated' | 'attendanceEndpoint'> & {
  messages: Pick<ListingProps['messages'], 'startingFrom' | 'endTime' | 'cancelled' | 'today' | 'loginPrompt' | 'loadingFriends' | 'attendingSuffix' | 'invite'>;
};

/** Card image that tries the next stored image when one fails and drops the
 * image area when none load, instead of showing a broken picture (#579). */
export function CardImage({ sources, alt }: { sources: string[]; alt: string }) {
  const [index, setIndex] = useState(0);
  const image = useRef<HTMLImageElement>(null);
  const src = sources[index];
  useEffect(() => {
    // A server-rendered image may already have failed before hydration.
    const element = image.current;
    if (element && element.complete && element.naturalWidth === 0) setIndex(current => current + 1);
  }, [src]);
  if (!src) return null;
  return <div className="demo-card-image"><img ref={image} src={src} alt={alt} loading="lazy"
    onError={() => setIndex(current => current + 1)} /></div>;
}

export function DemonstrationCard({ event, props, friends }: {
  event: Demonstration; props: CardProps; friends: Friend[] | null;
}) {
  const text = props.messages;
  const tags = Array.isArray(event.tags) ? event.tags.filter(tag => typeof tag === 'string') : [];
  const pride = tags.some(tag => tag.toLowerCase() === 'pride');
  const covers = [...new Set([event.cover_picture, event.cover_image, event.preview_image, event.img]
    .filter((value): value is string => typeof value === 'string' && value.length > 0))];
  const href = eventHref(event, props);
  const start = clockLabel(event.start_time_display) || clockLabel(event.start_time);
  const end = clockLabel(event.end_time_display) || clockLabel(event.end_time);
  const clock = start ? (end ? `${start}–${end}` : `${start} ${text.startingFrom}`)
    : end ? `${text.endTime}: ${end}` : '';
  const today = new Date();
  const localDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
  return <div className={`grid-item demo-card${pride ? ' demo-card-pride' : ''}`}
    data-demo-id={event._id} data-href={href} tabIndex={0} role="link" aria-label={event.title}
    onKeyDown={event => { if (event.target === event.currentTarget && event.key === 'Enter') window.location.assign(href); }}
    onClick={event => {
      if (!(event.target as Element).closest('a, button')) window.location.assign(href);
    }}>
    <div className="demo-card-badges">
      {event.cancelled && <span className="demo-badge cancelled-badge">{text.cancelled}</span>}
      {event.date === localDate && <span className="demo-badge today-badge">{text.today}</span>}
      {pride && <span className="demo-badge pride-badge">Pride</span>}
    </div>
    {covers.length > 0 && <CardImage key={covers.join('\n')} sources={covers} alt={event.title || ''} />}
    <div className="demo-card-title"><a href={href}><span>{event.title}</span></a></div>
    <div className="demo-card-details">
      <div className="demo-card-date-time">
        <span className="demo-card-date"><i className="fa-regular fa-calendar" aria-hidden="true" /> {event.formatted_date || event.date_display || event.date}</span>
        {clock && <span className="demo-card-time"><i className="fa-regular fa-clock" aria-hidden="true" /> {clock}</span>}
      </div>
      <div className="demo-card-location-row">
        <span className="demo-card-city"><i className="fa-solid fa-city" aria-hidden="true" /> {event.city}</span>
        <span className="demo-card-address"><i className="fa-solid fa-location-dot" aria-hidden="true" /> {event.address}</span>
      </div>
      <div className="demo-card-tags">{tags.map(tag => <a key={tag} className="demo-card-tag"
        href={props.tagUrl.replace('__TAG__', encodeURIComponent(tag))}>#{tag}</a>)}</div>
    </div>
    <div className="demo-card-attending">
      {!props.authenticated ? <div className="demo-card-no-friends"><span className="login-prompt">{text.loginPrompt}</span></div>
        : friends === null ? <div className="attending-loading"><span>{text.loadingFriends}</span></div>
        : friends.length ? <div className="demo-card-friends">{friends.slice(0, 3).map((friend, index) =>
          <img key={index} className="friend-avatar" src={friend.avatar} alt={friend.name} title={friend.name} />)}
          <span className="friends-text">{friends[0].name} {text.attendingSuffix}</span></div>
        : <a className="demo-card-no-friends" href={inviteHref(href)}><span className="plus-avatar">+</span><span className="invite-text">{text.invite}</span></a>}
    </div>
  </div>;
}

/** One batch per mounted page. Eviction/unmount aborts only that page's request. */
export function DemonstrationCards({ events, props }: { events: Demonstration[]; props: CardProps }) {
  const [friends, setFriends] = useState<Record<string, Friend[]> | null>(null);
  useEffect(() => {
    if (!props.authenticated || !events.length) return;
    const controller = new AbortController();
    async function load() {
      try {
        const response = await fetch(props.attendanceEndpoint, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
          body: JSON.stringify({ demo_ids: events.map(event => event._id) }), signal: controller.signal,
        });
        if (!response.ok) throw new Error('Attendance request failed');
        const data: unknown = await response.json();
        if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Invalid attendance');
        const safe: Record<string, Friend[]> = {};
        for (const event of events) {
          const rows = (data as Record<string, unknown>)[event._id];
          safe[event._id] = Array.isArray(rows) ? rows.filter(row => row && typeof row.name === 'string'
            && (!row.avatar || typeof row.avatar === 'string')) : [];
        }
        if (!controller.signal.aborted) setFriends(safe);
      } catch {
        // Optional attendance never blocks navigation or leaves a permanent spinner.
        if (!controller.signal.aborted) setFriends({});
      }
    }
    void load();
    return () => controller.abort();
  }, [events, props]);
  return <>{events.map(event => <DemonstrationCard key={event._id} event={event} props={props}
    friends={friends ? friends[event._id] || [] : null} />)}</>;
}
