import { Fragment } from 'react';
import { groupCities } from '../../app/cities';
import type { CitySummary } from '../../app/cities';

export function CityDirectory({ cities, loading = false, showJumpLinks = true }: { cities: CitySummary[]; loading?: boolean; showJumpLinks?: boolean }) {
  const groups = groupCities(cities);
  return <div className="city-directory" id="city-directory" aria-busy={loading}>
    {showJumpLinks && groups.length > 0 && <nav className="city-letter-links" aria-label="Kaupungit">
      {groups.map(group => <Fragment key={group.letter}><a href={`#city-letter-${group.letter}`}>{group.letter}</a>{' '}</Fragment>)}
    </nav>}
    {groups.map(group => <section className="city-letter-group" key={group.letter} aria-labelledby={`city-letter-${group.letter}`}>
      <h2 id={`city-letter-${group.letter}`}>{group.letter}</h2>
      <ul>{group.cities.map(city => <li key={city.key} data-city-key={city.key}>
        <a className="city-main-link" href={`/city/${city.key}`}><span className="city-name">{city.name}</span>
          {city.upcoming_count > 0 && <>{' '}<span className="city-upcoming" aria-hidden="true">({city.upcoming_count})</span>
            <span className="city-link-context visually-hidden"> {city.upcoming_count === 1 ? '1 tuleva mielenosoitus' : `${city.upcoming_count} tulevaa mielenosoitusta`}</span></>}</a>{' '}
        {city.today_count > 0 && <a className="city-today-count" href={`/city/${city.key}/tanaan`}>Tänään {city.today_count} {city.today_count === 1 ? 'mielenosoitus' : 'mielenosoitusta'}<span className="city-link-context visually-hidden">: {city.name}</span></a>}
      </li>)}</ul>
    </section>)}
  </div>;
}
