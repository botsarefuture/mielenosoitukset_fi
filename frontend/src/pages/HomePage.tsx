import { useEffect, useState } from 'react';
import { DemonstrationCards } from '../components/listings/DemonstrationCard';
import '../../../mielenosoitukset_fi/static/css/public-detail.css';
import type { CardProps } from '../components/listings/DemonstrationCard';
import type { Demonstration } from '../components/listings/types';

export type HomeProps = {
  endpoint: string; locale: string; cards: CardProps;
  urls: { all: string; submit: string; calendar: string; info: string; pride: string };
  text: { title: string; intro: string; search: string; searchPlaceholder: string; submitSearch: string;
    all: string; submit: string; calendar: string; info: string; eventsTitle: string;
    emptyTitle: string; empty: string; prideTitle: string; prideIntro: string; prideLink: string;
    recommendedTitle: string; loading: string; loadError: string; retry: string };
  /** Optional pre-fetched batch. Without it the component requests the public API. */
  initialData?: HomeData | null;
  /** Date shortcuts and the end-of-picks exit. Hosts without them keep the plain links. */
  quick?: { todayUrl: string; text: QuickText };
};

export type QuickText = { nav: string; today: string; weekend: string; all: string };

/** Maintainer decision (12 November 2026): the Pride banner rests until this
 * Helsinki date, then returns as a strip after the end-of-picks button. */
export const PRIDE_BANNER_FROM = '2027-01-01';

/** Today's date in Helsinki as YYYY-MM-DD. */
export function helsinkiDate(now = new Date()) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Helsinki', year: 'numeric', month: '2-digit', day: '2-digit' }).format(now);
}

/** The coming weekend, Saturday to Sunday, as Helsinki's own events calendar
 * uses it. On Saturday it is today and tomorrow, on Sunday only today. */
export function weekendRange(today: string): { start: string; end: string } {
  const day = new Date(`${today}T12:00:00Z`);
  const weekday = day.getUTCDay();
  const shift = (base: Date, days: number) => new Date(base.getTime() + days * 86_400_000).toISOString().slice(0, 10);
  if (weekday === 0) return { start: today, end: today };
  const saturday = shift(day, 6 - weekday);
  return { start: saturday, end: shift(new Date(`${saturday}T12:00:00Z`), 1) };
}

export type HomeData = { events: Demonstration[]; recommended: boolean };

/** Server rendering has no location; the render entry supplies the public origin. */
function pageOrigin() {
  if (typeof window !== 'undefined') return window.location.origin;
  return (globalThis as { __MOSO_ORIGIN__?: string }).__MOSO_ORIGIN__ ?? '';
}

/** Portable browser consumer: the host only supplies bootstrap configuration. */
export function HomePage({ endpoint, locale, cards, urls, text, initialData = null, quick }: HomeProps) {
  const today = helsinkiDate();
  const pride = today >= PRIDE_BANNER_FROM;
  const weekend = weekendRange(today);
  const weekendUrl = `${urls.all}?${new URLSearchParams({ date_start: weekend.start, date_end: weekend.end })}`;
  const [data, setData] = useState<HomeData | null>(initialData);
  const [failed, setFailed] = useState(false);
  const [attempt, retry] = useState(0);
  useEffect(() => {
    // A supplied batch is already displayed; only retries request it again.
    if (attempt === 0 && initialData) return;
    const controller = new AbortController();
    let active = true;
    const timeout = window.setTimeout(() => controller.abort(), 8000);
    setData(null); setFailed(false);
    async function load() {
      try {
        const url = new URL(endpoint, pageOrigin() || window.location.origin);
        url.searchParams.set('lang', locale);
        const response = await fetch(url, { signal: controller.signal, credentials: 'omit', headers: { Accept: 'application/json' } });
        if (!response.ok) throw new Error('Home data unavailable');
        const value = await response.json() as HomeData;
        if (!Array.isArray(value.events) || value.events.length > 50 || typeof value.recommended !== 'boolean'
          || !value.events.every(event => event && typeof event._id === 'string' && typeof event.title === 'string')) throw new Error('Invalid home data');
        if (active) setData(value);
      } catch { if (active) setFailed(true); }
      finally { window.clearTimeout(timeout); }
    }
    void load();
    return () => { active = false; window.clearTimeout(timeout); controller.abort(); };
  }, [endpoint, locale, attempt, initialData]);
  return <div className="home-page public-demonstration-list">
    <header className="home-intro">
      <div><h1>{text.title}</h1><p>{text.intro}</p></div>
      <a className="detail-button" href={urls.submit}>{text.submit}</a>
      <form className="home-search" action={urls.all} method="get" role="search">
        <label htmlFor="home-search">{text.search}</label>
        <div><input id="home-search" name="search" type="search" placeholder={text.searchPlaceholder} />
          <button className="detail-button detail-button--primary" type="submit">{text.submitSearch}</button></div>
      </form>
      {quick && <nav className="home-quick" aria-label={quick.text.nav}>
        <a href={quick.todayUrl}>{quick.text.today}</a>
        <a href={weekendUrl}>{quick.text.weekend}</a>
      </nav>}
      <nav className="home-links" aria-label={text.title}>
        <a href={urls.all}>{text.all} <span aria-hidden="true">→</span></a>
        <a href={urls.calendar}>{text.calendar}</a><a href={urls.info}>{text.info}</a>
      </nav>
    </header>
    <section className="home-events" aria-labelledby="home-events-title">
      <div className="home-section-heading"><h2 id="home-events-title">{data?.recommended ? text.recommendedTitle : text.eventsTitle}</h2>
        {!quick && <a href={urls.all}>{text.all} <span aria-hidden="true">→</span></a>}</div>
      {failed ? <div className="home-status"><p role="alert">{text.loadError}</p><button className="home-button" onClick={() => retry(value => value + 1)}>{text.retry}</button></div>
        : !data ? <p className="home-status" role="status">{text.loading}</p>
        : data.events.length ? <div className="demos-grid"><DemonstrationCards events={data.events} props={cards} /></div>
        : <div className="home-empty"><h3>{text.emptyTitle}</h3><p>{text.empty}</p><a href={urls.submit}>{text.submit}</a></div>}
    </section>
    {/* One clear exit after the picks; the listing page has the filters and paging. */}
    {quick && <a className="home-all-link" href={urls.all}>{quick.text.all} <span aria-hidden="true">→</span></a>}
    {/* After the exit, so the campaign is never read as "more events". */}
    {pride && <aside className="home-campaign"><div><h2>{text.prideTitle}</h2><p>{text.prideIntro}</p></div>
      <a className="home-button home-button--secondary" href={urls.pride}>{text.prideLink}</a></aside>}
  </div>;
}
