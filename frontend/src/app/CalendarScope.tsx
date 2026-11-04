import { cityCatalog } from './cities';
import { monthPath } from './calendar';
import type { CalendarMonth } from './calendar';

/** Native GET fallback and React navigation use the same catalog and URL. */
export function CalendarScope({ period }: { period: CalendarMonth }) {
  return <form className="calendar-scope" action={monthPath({ ...period, city: undefined })} method="get"
    onSubmit={event => { event.preventDefault();
      const city = String(new FormData(event.currentTarget).get('city') ?? '');
      window.location.assign(monthPath({ ...period, city: city || undefined }));
    }}>
    <div><label htmlFor="calendar-city">Alue</label><select id="calendar-city" name="city" defaultValue={period.city ?? ''}>
      <option value="">Koko Suomi</option>{cityCatalog.map(city => <option key={city.key} value={city.key}>{city.name}</option>)}
    </select></div><button type="submit">Näytä kalenteri</button>
  </form>;
}
