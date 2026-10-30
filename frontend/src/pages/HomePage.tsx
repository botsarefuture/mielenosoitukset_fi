import { DemonstrationCards } from '../components/listings/DemonstrationCard';
import type { CardProps } from '../components/listings/DemonstrationCard';
import type { Demonstration } from '../components/listings/types';

export type HomeProps = {
  endpoint: string; locale: string; cards: CardProps;
  urls: { all: string; submit: string; calendar: string; info: string; pride: string };
  text: { title: string; intro: string; search: string; searchPlaceholder: string; submitSearch: string;
    all: string; submit: string; calendar: string; info: string; eventsTitle: string;
    emptyTitle: string; empty: string; prideTitle: string; prideIntro: string; prideLink: string;
    recommendedTitle: string; loading: string; loadError: string; retry: string };
};

type HomeData = { events: Demonstration[]; recommended: boolean };

/** Portable browser consumer: Flask only supplies bootstrap configuration. */
export function HomePage({ endpoint, locale, cards, urls, text }: HomeProps) {
  const [data, setData] = useState<HomeData | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, retry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const timeout = window.setTimeout(() => controller.abort(), 8000);
    setData(null); setFailed(false);
    async function load() {
      try {
        const url = new URL(endpoint, window.location.origin);
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
  }, [endpoint, locale, attempt]);
  return <div className="home-page public-demonstration-list">
    <header className="home-intro">
      <div><h1>{text.title}</h1><p>{text.intro}</p></div>
      <a className="home-button home-button--secondary" href={urls.submit}>{text.submit}</a>
      <form className="home-search" action={urls.all} method="get" role="search">
        <label htmlFor="home-search">{text.search}</label>
        <div><input id="home-search" name="search" type="search" placeholder={text.searchPlaceholder} />
          <button className="home-button" type="submit">{text.submitSearch}</button></div>
      </form>
      <nav className="home-links" aria-label={text.title}>
        <a href={urls.all}>{text.all} <span aria-hidden="true">→</span></a>
        <a href={urls.calendar}>{text.calendar}</a><a href={urls.info}>{text.info}</a>
      </nav>
    </header>
    <section className="home-events" aria-labelledby="home-events-title">
      <div className="home-section-heading"><h2 id="home-events-title">{data?.recommended ? text.recommendedTitle : text.eventsTitle}</h2><a href={urls.all}>{text.all} <span aria-hidden="true">→</span></a></div>
      {failed ? <div className="home-status"><p role="alert">{text.loadError}</p><button className="home-button" onClick={() => retry(value => value + 1)}>{text.retry}</button></div>
        : !data ? <p className="home-status" role="status">{text.loading}</p>
        : data.events.length ? <div className="demos-grid"><DemonstrationCards events={data.events} props={cards} /></div>
        : <div className="home-empty"><h3>{text.emptyTitle}</h3><p>{text.empty}</p><a href={urls.submit}>{text.submit}</a></div>}
    </section>
    <aside className="home-campaign"><div><h2>{text.prideTitle}</h2><p>{text.prideIntro}</p></div>
      <a className="home-button home-button--secondary" href={urls.pride}>{text.prideLink}</a></aside>
  </div>;
}
import { useEffect, useState } from 'react';
