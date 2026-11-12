import { dateForDay, monthLength, monthName, monthPath } from './calendar';
import type { CalendarMonth } from './calendar';
import { dayLabel, helsinkiDay } from './cities';

/** One accessible seven-column grid for month and annual overviews. */
export function CalendarGrid({ period, days, selected, overview = false }: {
  period: CalendarMonth; days: { date: string; count: number }[]; selected?: number; overview?: boolean;
}) {
  const firstWeekday = (new Date(Date.UTC(period.year, period.month - 1, 1)).getUTCDay() + 6) % 7;
  const length = monthLength(period);
  const cells = Math.ceil((firstWeekday + length) / 7) * 7;
  const counts = new Map(days.map(row => [row.date, row.count]));
  const today = helsinkiDay();
  return <table className="month-calendar-grid"><caption className="calendar-sr-only">{monthName(period)}</caption>
    <thead><tr>{['Ma','Ti','Ke','To','Pe','La','Su'].map(name => <th key={name} scope="col">{name}</th>)}</tr></thead>
    <tbody>{Array.from({ length: cells / 7 }, (_, week) => <tr key={week}>{Array.from({ length: 7 }, (_, weekday) => {
      const day = week * 7 + weekday - firstWeekday + 1;
      if (day < 1 || day > length) return <td key={weekday} />;
      const date = dateForDay(period, day);
      const count = counts.get(date) ?? 0;
      // An annual overview needs links to event days, not hundreds of empty
      // keyboard stops. The month heading still opens every date in that month.
      if (overview && count === 0) return <td key={weekday}><span className={`calendar-static-day${date === today ? ' is-today' : ''}`}>
        <span>{day}</span>{date === today && <span className="calendar-sr-only">Tänään</span>}
      </span></td>;
      return <td key={weekday}><a href={`${monthPath(period)}?day=${day}#calendar-agenda`} aria-current={selected === day ? 'date' : undefined}
        className={date === today ? 'is-today' : undefined}
        aria-label={`${dayLabel(date)}, ${count} mielenosoitusta${date === today ? ', tänään' : ''}`}>
        <span>{day}</span>{count > 0 && <span className="calendar-day-count" aria-hidden="true">{count}</span>}
      </a></td>;
    })}</tr>)}</tbody>
  </table>;
}
