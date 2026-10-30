import { DemonstrationCards } from '../components/listings/DemonstrationCard';
import type { CardProps } from '../components/listings/DemonstrationCard';
import type { Demonstration } from '../components/listings/types';

type HomeProps = {
  events: Demonstration[]; cards: CardProps;
  urls: { all: string; submit: string; calendar: string; info: string; pride: string };
  text: { title: string; intro: string; search: string; searchPlaceholder: string; submitSearch: string;
    all: string; submit: string; calendar: string; info: string; eventsTitle: string;
    emptyTitle: string; empty: string; prideTitle: string; prideIntro: string; prideLink: string };
};

/** Initial events arrive with the HTML, without a second content request. */
export function HomePage({ events, cards, urls, text }: HomeProps) {
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
      <div className="home-section-heading"><h2 id="home-events-title">{text.eventsTitle}</h2><a href={urls.all}>{text.all} <span aria-hidden="true">→</span></a></div>
      {events.length ? <div className="demos-grid"><DemonstrationCards events={events} props={cards} /></div>
        : <div className="home-empty"><h3>{text.emptyTitle}</h3><p>{text.empty}</p><a href={urls.submit}>{text.submit}</a></div>}
    </section>
    <aside className="home-campaign"><div><h2>{text.prideTitle}</h2><p>{text.prideIntro}</p></div>
      <a className="home-button home-button--secondary" href={urls.pride}>{text.prideLink}</a></aside>
  </div>;
}
