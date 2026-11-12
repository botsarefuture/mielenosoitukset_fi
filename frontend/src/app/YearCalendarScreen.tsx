import type { CalendarBootstrap } from './calendar';
import { calendarPlace, currentMonth, monthName, monthPath } from './calendar';
import { CalendarGrid } from './CalendarGrid';
import { CalendarScope } from './CalendarScope';
import './calendar.css';

export default function YearCalendarScreen({ calendar }: { calendar: CalendarBootstrap }) {
  const { year, data } = calendar;
  return <article className="month-calendar year-calendar">
    <header className="month-calendar-heading"><div><h1>Mielenosoituskalenteri {year}</h1><p>Mielenosoitukset {calendarPlace(calendar)}. Valitse kuukausi tai päivä.</p></div>
      <a className="calendar-submit" href={monthPath({ ...currentMonth(), city: calendar.city })}>Tämä kuukausi</a></header>
    <CalendarScope period={calendar} />
    <nav className="month-calendar-nav year-calendar-nav" aria-label="Vuoden valinta">
      {year > 2000 && <a href={monthPath({ ...calendar, year: year-1 })} aria-label={`Edellinen vuosi: ${year-1}`}>← {year-1}</a>}
      <a href={monthPath({ ...calendar, year: currentMonth().year })}>Tämä vuosi</a>
      {year < 2100 && <a href={monthPath({ ...calendar, year: year+1 })} aria-label={`Seuraava vuosi: ${year+1}`}>{year+1} →</a>}
    </nav>
    {!data ? <div role="alert" className="calendar-notice"><p>Kalenterin lataaminen epäonnistui.</p><button onClick={() => window.location.reload()}>Yritä uudelleen</button></div> : <>
      <p className="month-calendar-summary">{data.total} {data.total === 1 ? 'mielenosoitus' : 'mielenosoitusta'} vuonna {year}. Päivän numeron alla näkyy mielenosoitusten määrä.</p>
      <div className="year-calendar-months">{Array.from({ length:12 }, (_, index) => {
        const period = { ...calendar, month: index+1 };
        const days = data.days.filter(row => Number(row.date.slice(5,7)) === period.month);
        const total = days.reduce((sum,row) => sum+row.count,0);
        return <section className="month-calendar-panel" key={period.month} aria-labelledby={`calendar-month-${period.month}`}>
          <h2 id={`calendar-month-${period.month}`}><a href={monthPath(period)}>{monthName(period)}</a></h2>
          <p>{total} {total === 1 ? 'mielenosoitus' : 'mielenosoitusta'}</p>
          <CalendarGrid period={period} days={days} overview />
        </section>;
      })}</div>
    </>}
  </article>;
}
