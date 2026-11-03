import { useEffect, useState } from 'react';
import { adjacentMonth, currentMonth, dateForDay, monthLength, monthName, monthPath } from './calendar';
import type { CalendarBootstrap } from './calendar';
import type { AppConfig } from './config';
import type { SessionSummary } from './session';
import { dayLabel, helsinkiDay } from './cities';
import { listingProps, validListingPage } from './listing';
import type { Page } from '../components/listings/types';
import { DemonstrationCards } from '../components/listings/DemonstrationCard';
import '../components/listings/react-listing.css';
import './calendar.css';

export default function CalendarScreen({ calendar, config, session }: {
  calendar: CalendarBootstrap; config: AppConfig; session: SessionSummary;
}) {
  const { data, day, page } = calendar;
  const date = dateForDay(calendar, day);
  const count = data?.days.find(row => row.date === date)?.count ?? 0;
  const [events, setEvents] = useState<Page | null>(calendar.events ?? null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const props = listingProps({ name: 'listing', scope: 'all' }, config, session);
  useEffect(() => {
    if (window.location.hash === '#calendar-agenda') {
      const heading = document.getElementById('calendar-day');
      document.getElementById('calendar-agenda')?.scrollIntoView({ block: 'start' });
      heading?.focus({ preventScroll: true });
    }
  }, [date, page]);
  useEffect(() => {
    if (calendar.events && attempt === 0) { setEvents(calendar.events); setFailed(false); return; }
    setEvents(null); setFailed(false);
    if (!data || count === 0) return;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10_000);
    const query = new URLSearchParams({ date_start: date, date_end: date, in_past: 'true', lang: config.locale, page: String(page), per_page: '20' });
    void fetch(`${config.apiBase}/demonstrations?${query}`, { signal: controller.signal, credentials: 'omit' })
      .then(async response => {
        if (!response.ok) throw new Error('Calendar day unavailable');
        const result: unknown = await response.json();
        if (!validListingPage(result) || result.results.some(event => event.date !== date)) throw new Error('Invalid calendar day');
        if (!controller.signal.aborted) setEvents(result);
      }).catch(() => { if (!disposed) setFailed(true); })
      .finally(() => clearTimeout(timer));
    let disposed = false;
    return () => { disposed = true; clearTimeout(timer); controller.abort(); };
  }, [date, page, count, data, config.apiBase, config.locale, attempt, calendar.events]);
  const previous = adjacentMonth(calendar, -1);
  const next = adjacentMonth(calendar, 1);
  const firstWeekday = (new Date(Date.UTC(calendar.year, calendar.month - 1, 1)).getUTCDay() + 6) % 7;
  const cells = Math.ceil((firstWeekday + monthLength(calendar)) / 7) * 7;
  const href = (selected: number, page = 1) => `${monthPath(calendar)}?day=${selected}${page > 1 ? `&page=${page}` : ''}#calendar-agenda`;
  return <article className="month-calendar">
    <header className="month-calendar-heading"><div><h1>Mielenosoituskalenteri</h1><p>Valitse päivä ja katso sen mielenosoitukset.</p></div>
      <a className="calendar-submit" href={config.urls.submit}>Ilmoita mielenosoituksesta</a></header>
    <section className="month-calendar-panel" aria-labelledby="calendar-month">
      <div className="month-calendar-nav"><h2 id="calendar-month">{monthName(calendar)}</h2>
        <nav aria-label="Kuukauden valinta">
          {previous.year >= 2000 && <a href={monthPath(previous)} aria-label={`Edellinen kuukausi: ${monthName(previous)}`}>← Edellinen</a>}
          <a href={monthPath(currentMonth())}>Tämä kuukausi</a>
          {next.year <= 2100 && <a href={monthPath(next)} aria-label={`Seuraava kuukausi: ${monthName(next)}`}>Seuraava →</a>}
        </nav></div>
      {!data ? <div role="alert" className="calendar-notice"><p>Kalenterin lataaminen epäonnistui.</p><button onClick={() => window.location.reload()}>Yritä uudelleen</button></div> : <>
        <p className="month-calendar-summary">{data.total} {data.total === 1 ? 'mielenosoitus' : 'mielenosoitusta'} tässä kuussa. Päivän numeroiden alla näkyy mielenosoitusten määrä.</p>
        <table className="month-calendar-grid"><caption className="calendar-sr-only">{monthName(calendar)}</caption>
          <thead><tr>{['Ma', 'Ti', 'Ke', 'To', 'Pe', 'La', 'Su'].map(name => <th key={name} scope="col">{name}</th>)}</tr></thead>
          <tbody>{Array.from({ length: cells / 7 }, (_, week) => <tr key={week}>{Array.from({ length: 7 }, (_, weekday) => {
            const number = week * 7 + weekday - firstWeekday + 1;
            if (number < 1 || number > monthLength(calendar)) return <td key={weekday} />;
            const value = dateForDay(calendar, number);
            const total = data.days.find(row => row.date === value)?.count ?? 0;
            return <td key={weekday}><a href={href(number)} aria-current={day === number ? 'date' : undefined}
              className={value === helsinkiDay() ? 'is-today' : undefined}
              aria-label={`${dayLabel(value)}, ${total} mielenosoitusta${value === helsinkiDay() ? ', tänään' : ''}`}>
              <span>{number}</span>{total > 0 && <span className="calendar-day-count" aria-hidden="true">{total}</span>}
            </a></td>;
          })}</tr>)}</tbody>
        </table>
        <div className="month-calendar-links"><span>Tänään on {dayLabel(helsinkiDay())}</span><a href={`/calendar/${calendar.year}/`}>Vuosi {calendar.year}</a></div>
      </>}
    </section>
    {data && <section className="calendar-agenda public-demonstration-list" id="calendar-agenda" aria-labelledby="calendar-day">
      <h2 id="calendar-day" tabIndex={-1}>{dayLabel(date)}</h2>
      {count === 0 ? <div className="calendar-notice"><p>Tälle päivälle ei ole ilmoitettu mielenosoituksia.</p><a href={config.urls.demonstrations}>Katso tulevat mielenosoitukset</a></div>
        : failed ? <div role="alert" className="calendar-notice"><p>Mielenosoitusten lataaminen epäonnistui.</p><button onClick={() => setAttempt(value => value + 1)}>Yritä uudelleen</button></div>
        : !events ? <p role="status">Ladataan mielenosoituksia...</p>
        : events.page > events.total_pages ? <div className="calendar-notice"><p>Tällä sivulla ei ole mielenosoituksia.</p><a href={href(day)}>Palaa päivän ensimmäiselle sivulle</a></div>
        : <><p role="status">{events.total === 0 ? 'Päivän tapahtumat ovat muuttuneet. Valitse toinen päivä tai päivitä sivu.' : `Näytetään ${events.result_start}–${events.result_end} / ${events.total} mielenosoituksesta`}</p>
          <div className="demos-grid"><DemonstrationCards events={events.results} props={props} /></div>
          {(events.total_pages > 1) && <nav className="calendar-pagination" aria-label="Päivän mielenosoitusten sivut">
            {page > 1 && <a href={href(day, page - 1)}>← Edellinen sivu</a>}
            <span>Sivu {events.page} / {events.total_pages}</span>
            {page < events.total_pages && <a href={href(day, page + 1)}>Seuraava sivu →</a>}
          </nav>}</>}
    </section>}
  </article>;
}
