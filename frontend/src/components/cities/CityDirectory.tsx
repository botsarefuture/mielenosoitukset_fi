import { groupCities } from '../../app/cities';
import type { CitySummary } from '../../app/cities';

export function CityDirectory({ cities, loading = false }: { cities: CitySummary[]; loading?: boolean }) {
  return <div className="city-directory" id="city-directory" aria-busy={loading}>
    {groupCities(cities).map(group => <section className="city-letter-group" key={group.letter} aria-labelledby={`city-letter-${group.letter}`}>
      <h2 id={`city-letter-${group.letter}`}>{group.letter}</h2>
      <ul>{group.cities.map(city => <li key={city.key} data-city-key={city.key}>
        <a className="city-main-link" href={`/city/${city.key}`}><span className="city-name">{city.name}</span>{' '}
          <span className="city-upcoming">{city.upcoming_count === 1 ? '1 tuleva mielenosoitus' : city.upcoming_count ? `${city.upcoming_count} tulevaa mielenosoitusta` : 'Ei tulevia mielenosoituksia'}</span></a>{' '}
        {city.today_count > 0 && <a className="city-today-count" href={`/city/${city.key}/tanaan`}>Tänään {city.today_count} {city.today_count === 1 ? 'mielenosoitus' : 'mielenosoitusta'}<span className="city-link-context">: {city.name}</span></a>}
      </li>)}</ul>
    </section>)}
  </div>;
}
