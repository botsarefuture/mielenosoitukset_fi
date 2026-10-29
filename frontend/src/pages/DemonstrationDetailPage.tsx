import { Component, lazy, Suspense, useEffect, useMemo, useState, useTransition } from 'react';
import type { ReactNode } from 'react';
import { DetailActionDialog, Participation } from '../components/detail/DetailActions';
import type { DialogKind } from '../components/detail/DetailActions';
import { FollowButton } from '../components/detail/FollowButton';
import { DetailGallery } from '../components/detail/DetailGallery';
import { clockLabel, dateLabel, safeHref, sanitizeDescription } from '../components/detail/content';
import { useDemonstration } from '../components/detail/useDemonstration';
import type { DetailEvent, DetailProps } from '../components/detail/types';
export type { DetailProps, DetailMessages } from '../components/detail/types';
const DetailMap = lazy(() => import('../components/detail/DetailMap'));

class MapBoundary extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}
function Icon({ name }: { name: string }) { return <i className={`fa-solid fa-${name}`} aria-hidden="true" />; }
function LinkButton({ href, children, primary = false }: { href: string; children: ReactNode; primary?: boolean }) {
  const safe = safeHref(href);
  return safe ? <a className={`detail-button${primary ? ' detail-button--primary' : ''}`} href={safe}>{children}</a> : null;
}
function EventDescription({ event, label }: { event: DetailEvent; label: string }) {
  const html = useMemo(() => sanitizeDescription(event.description), [event.description]);
  return html ? <section className="detail-section"><h2>{label}</h2><div className="detail-prose" dangerouslySetInnerHTML={{ __html: html }} /></section> : null;
}
function ShareActions({ url, messages }: { url: string; messages: DetailProps['messages'] }) {
  const [shareCopied, setCopied] = useState<'idle' | 'success' | 'error'>('idle');
  async function copy() {
    try { await navigator.clipboard.writeText(url); setCopied('success'); } catch { setCopied('error'); }
  }
  return <div className="detail-share"><button className="detail-button detail-button--quiet" type="button" onClick={() => void copy()}><Icon name="link" />{messages.copyLink}</button>
    <a className="detail-button detail-button--quiet" target="_blank" rel="noopener noreferrer" href={`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`} aria-label={messages.share}><Icon name="share-nodes" />{messages.shareFacebook}</a>
    <span role="status">{shareCopied === 'success' ? messages.shareCopied : shareCopied === 'error' ? messages.copyFailed : ''}</span>
  </div>;
}
function EventContent({ event, props }: { event: DetailEvent; props: DetailProps }) {
  const text = props.messages;
  const [mapVisible, showMap] = useState(false);
  const [dialog, setDialog] = useState<DialogKind | null>(null);
  useEffect(() => { if (props.initialAction === 'invite') { setDialog('invite'); props.onIntentConsumed?.(); } }, [props.initialAction, props.onIntentConsumed]);
  const time = [clockLabel(event.start_time), clockLabel(event.end_time)].filter(Boolean).join('–');
  const location = [event.address, event.city].filter(Boolean).join(', ');
  const source = (event.cover_source ?? '').toLowerCase();
  const manualCover = !['auto', 'automatic'].includes(source) && (source || event.cover_picture !== event.preview_image) ? event.cover_picture : null;
  const images = event.gallery_images.length ? event.gallery_images : [event.img || manualCover].filter((value): value is string => Boolean(value));
  const externalEvent = safeHref(event.facebook);
  const directions = event.latitude !== null && event.longitude !== null
    ? `https://www.openstreetmap.org/?mlat=${event.latitude}&mlon=${event.longitude}#map=17/${event.latitude}/${event.longitude}`
    : `https://www.openstreetmap.org/search?query=${encodeURIComponent(location)}`;
  return <>
    <header className="detail-heading">
      {event.cancelled && <p className="detail-cancelled" role="status"><Icon name="ban" />{text.cancelled}</p>}
      <h1>{event.title}</h1>
      <dl className="detail-facts"><div><dt><Icon name="calendar-days" />{text.date}</dt><dd>{dateLabel(event.date, props.locale)}<span>{time ? <>{time}{event.start_time && !event.end_time ? ` ${text.startingFrom}` : ''}</> : text.unknownTime}</span></dd></div>
        {location && <div><dt><Icon name="location-dot" />{text.location}</dt><dd>{location}</dd></div>}</dl>
      <div className="detail-actions">
        {!event.cancelled && <><button type="button" className="detail-button detail-button--primary" onClick={() => setDialog('reminder')}><Icon name="bell" />{text.reminder}</button>
          <LinkButton href={props.urls.calendar}><Icon name="calendar-plus" />{text.calendar}</LinkButton></>}
        <button type="button" className="detail-button" onClick={() => setDialog('report')}><Icon name="flag" />{text.report}</button>
      </div>
      {props.authenticated && props.recurringTargetId && !event.cancelled && <FollowButton props={props} />}
    </header>
    <div className="detail-layout"><div className="detail-main">
      <DetailGallery key={event._id} images={images} title={event.title} messages={text} />
      <EventDescription event={event} label={text.description} />
      {event.route.length > 0 && <section className="detail-section"><h2>{text.route}</h2><ol className="detail-route">{event.route.map((stop, index) => <li key={`${index}-${stop}`}>{stop}</li>)}</ol></section>}
      <section className="detail-section"><h2>{text.organizers}</h2>{event.organizers.length ? <ul className="detail-organizers">{event.organizers.map((organizer, index) => <li key={`${index}-${organizer.name}`}>
        <h3>{organizer.name || text.anonymousOrganizer}</h3><div>{organizer.organization_id && !organizer.is_private && <a href={safeHref(`${props.urls.organizationPrefix}${encodeURIComponent(organizer.organization_id)}`)}>{text.organizerProfile}</a>}{props.authenticated && organizer.organization_id && (props.followableOrganizations ?? []).includes(organizer.organization_id) && <FollowButton props={props} organizationId={organizer.organization_id} />}
        {safeHref(organizer.website) && <a href={safeHref(organizer.website)} target="_blank" rel="noopener noreferrer">{text.website}<Icon name="arrow-up-right-from-square" /></a>}
        {organizer.email && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(organizer.email) && <a href={`mailto:${encodeURIComponent(organizer.email)}`}>{organizer.email}</a>}</div>
      </li>)}</ul> : <p className="detail-note">{text.noOrganizers}</p>}</section>
      {event.tags.length > 0 && <div className="detail-tags">{event.tags.map(tag => <a key={tag} href={safeHref(`${props.urls.tagPrefix}${encodeURIComponent(tag)}`)}>#{tag}</a>)}</div>}
      {externalEvent && <LinkButton href={externalEvent}>{text.facebook}</LinkButton>}
    </div><aside className="detail-aside">
      <section className="detail-section detail-location"><h2>{text.location}</h2><p>{location}</p><a href={directions} target="_blank" rel="noopener noreferrer">{text.directions}<Icon name="arrow-up-right-from-square" /></a>
        {event.latitude !== null && event.longitude !== null && (mapVisible
          ? <MapBoundary fallback={<p>{text.error}</p>}><Suspense fallback={<p role="status">{text.mapLoading}</p>}><DetailMap latitude={event.latitude} longitude={event.longitude} messages={text} /></Suspense></MapBoundary>
          : <button className="detail-button" type="button" onClick={() => showMap(true)}><Icon name="map" />{text.showMap}</button>)}
      </section>
      {!event.cancelled && <section className="detail-section"><h2>{text.attend}</h2><Participation event={event} props={props} /><button type="button" className="detail-button" onClick={() => setDialog('invite')}>{text.invite}</button></section>}
      <section className="detail-section"><h2>{text.share}</h2><ShareActions url={props.canonicalUrl} messages={text} /></section>
    </aside></div>
    {dialog && <DetailActionDialog key={dialog} kind={dialog} event={event} props={props} close={() => setDialog(null)} />}
  </>;
}

function SeriesNavigation({ props }: { props: DetailProps }) {
  const [pending, startTransition] = useTransition();
  const text = props.messages;
  return <>{props.series && <nav className="detail-series" aria-label={props.series.title} aria-busy={pending}>
      <h2>{props.series.title}</h2><div className="detail-series__items">{props.series.occurrences.map(item => <a key={item.id}
        href={safeHref(item.url)} aria-current={item.id === props.id ? 'page' : undefined} className={item.cancelled ? 'is-cancelled' : ''}
        onClick={e => { if (!props.onSelect || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return; e.preventDefault(); startTransition(() => props.onSelect?.(item.id, item.url)); }}>
        <span>{dateLabel(item.date, props.locale)}</span><small>{item.cancelled ? text.cancelled : clockLabel(item.start_time ?? null)}</small>
      </a>)}</div>
    </nav>}</>;
}

/** Portable screen: host supplies routes, translations and navigation adapter. */
export function DemonstrationDetailPage(props: DetailProps) {
  const { state, retry } = useDemonstration(props.endpoint, props.id, props.locale);
  useEffect(() => { if (state.status === 'ready') props.onLoaded?.(state.event); }, [state, props.onLoaded]);
  let content: ReactNode;
  if (state.status === 'loading') content = <div className="detail-loading" role="status" aria-busy="true"><span className="detail-loading__bar" />{props.messages.loading}</div>;
  else if (state.status === 'error' || state.status === 'not-found') content = <section className="detail-error" role="alert"><h1>{state.status === 'not-found' ? props.messages.notFound : props.messages.error}</h1><div className="detail-actions">
    {state.status === 'error' && <button type="button" className="detail-button detail-button--primary" onClick={retry}>{props.messages.retry}</button>}
    <LinkButton href={props.urls.listing}>{props.messages.allEvents}</LinkButton>
  </div></section>;
  else content = <EventContent key={state.event._id} event={state.event} props={props} />;
  return <article className="public-detail" aria-busy={state.status === 'loading'}><SeriesNavigation props={props} />{content}</article>;
}
