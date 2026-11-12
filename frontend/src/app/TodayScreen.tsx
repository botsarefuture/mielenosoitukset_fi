import { PublicListingPage } from '../pages/PublicListingPage';
import { dayLabel, findCity, helsinkiDay } from './cities';
import { listingProps } from './listing';
import type { ListingBootstrap } from './listing';
import type { AppConfig } from './config';
import type { SessionSummary } from './session';
import { useDayRollover } from '../components/cities/useDayRollover';
import '../components/cities/cities.css';

export default function TodayScreen({ city: value, listing, config, session }: {
  city?: string; listing?: ListingBootstrap; config: AppConfig; session: SessionSummary;
}) {
  const city = value ? findCity(value) : undefined;
  const day = listing?.page?.day ?? helsinkiDay();
  useDayRollover(day);
  const props = listingProps({ name: 'listing', scope: city ? 'city-today' : 'today', value: city?.key }, config, session);
  return <article className="city-discovery">
    <nav aria-label="Murupolku"><ol className="discovery-breadcrumbs"><li><a href="/">Etusivu</a></li>
      <li><a href="/cities">Kaupungit</a></li>{city && <li><a href={`/city/${city.key}`}>{city.name}</a></li>}<li aria-current="page">Tänään</li></ol></nav>
    <div className="today-context"><p>{dayLabel(day)}</p><a href={city ? `/city/${city.key}` : '/demonstrations'}>Katso myös tulevat mielenosoitukset</a></div>
    <PublicListingPage {...props} initialData={listing?.page} initialSearch={listing?.query} />
  </article>;
}
