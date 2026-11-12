import { adjacentMonth, calendarPlace, dateForDay, monthName, monthPath } from './calendar';
import type { CalendarBootstrap } from './calendar';
import { CalendarScope } from './CalendarScope';
import { dayLabel } from './cities';
import { todayItems } from './discovery-meta';
import type { AppConfig } from './config';

/** React-owned readable discovery and event links when scripts are unavailable. */
export function CalendarFallback({ calendar, config }: { calendar: CalendarBootstrap; config: AppConfig }) {
  const { data, year, month, day, events, page } = calendar;
  const annual = month === 0;
  const previous = annual ? { ...calendar, year: year-1 } : adjacentMonth(calendar,-1);
  const next = annual ? { ...calendar, year: year+1 } : adjacentMonth(calendar,1);
  const eventLinks = todayItems(config, events ?? null);
  return <article className="container-main-content month-calendar">
    <a href="/">Mielenosoitukset.fi</a>
    <h1>{annual ? `Mielenosoituskalenteri ${year}` : monthName(calendar)}</h1>
    <p>Mielenosoitukset {calendarPlace(calendar)}.</p>
    <CalendarScope period={calendar} />
    <nav aria-label={annual ? 'Vuoden valinta' : 'Kuukauden valinta'}>
      {previous.year >= 2000 && <a href={monthPath(previous)}>{annual ? 'Edellinen vuosi' : 'Edellinen kuukausi'}</a>}{' · '}
      {next.year <= 2100 && <a href={monthPath(next)}>{annual ? 'Seuraava vuosi' : 'Seuraava kuukausi'}</a>}
      {!annual && <> · <a href={monthPath({ ...calendar, month:0 })}>Vuosi {year}</a></>}
    </nav>
    {!data ? <p>Kalenterin lataaminen epäonnistui. Yritä uudelleen.</p> : <>
      <p>{data.total} mielenosoitusta</p>
      {annual ? <ul>{Array.from({ length:12 }, (_, index) => {
        const period = { ...calendar, month:index+1 };
        const total = data.days.filter(row=>Number(row.date.slice(5,7))===period.month).reduce((sum,row)=>sum+row.count,0);
        return <li key={period.month}><a href={monthPath(period)}>{monthName(period)}</a>: {total} mielenosoitusta</li>;
      })}</ul> : <ul>{data.days.map(row => <li key={row.date}>
        <a href={`${monthPath(calendar)}?day=${Number(row.date.slice(8))}#calendar-agenda`}>{dayLabel(row.date)}: {row.count} mielenosoitusta</a>
      </li>)}</ul>}
      {!annual && events !== undefined && <section id="calendar-agenda"><h2>{dayLabel(dateForDay(calendar,day))}</h2>
        {events === null ? <p>Mielenosoitusten lataaminen epäonnistui. Päivitä sivu ja yritä uudelleen.</p> : <>
          <ul>{eventLinks.map((event,index) => <li key={event.url}><a href={event.url}>{event.name}</a>{' '}
            {[events.results[index].start_time,events.results[index].city,events.results[index].address].filter(Boolean).join(' · ')}
          </li>)}</ul>
          {events.total === 0 && <p>Tälle päivälle ei ole ilmoitettu mielenosoituksia.</p>}
          {page > events.total_pages && <a href={`?day=${day}#calendar-agenda`}>Palaa päivän ensimmäiselle sivulle</a>}
          <nav aria-label="Päivän mielenosoitusten sivut">
            {page > 1 && <a href={`?day=${day}&page=${page-1}#calendar-agenda`}>Edellinen sivu</a>}{' '}
            {page < events.total_pages && <a href={`?day=${day}&page=${page+1}#calendar-agenda`}>Seuraava sivu</a>}
          </nav>
        </>}
      </section>}
    </>}
    <a href={config.urls.demonstrations}>Kaikki mielenosoitukset</a>
  </article>;
}
