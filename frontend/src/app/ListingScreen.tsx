import { cityAdminPath } from './city-admin-route';
import { PublicListingPage } from '../pages/PublicListingPage';
import type { AppConfig } from './config';
import { listingProps } from './listing';
import type { ListingBootstrap, ListingRoute } from './listing';
import type { SessionSummary } from './session';

/** Keep listing filters, calendar and city data off the home-page load path. */
export default function ListingScreen({ route, config, session, listing }: {
  route: ListingRoute; config: AppConfig; session: SessionSummary; listing?: ListingBootstrap;
}) {
  // Nationally managed cities (Helsinki) and full local teams never recruit here.
  const status = route.scope === 'city' ? listing?.cityAdminStatus : undefined;
  const recruiting = status === 'none' || status === 'single' ? status : undefined;
  return <PublicListingPage {...listingProps(route, config, session)}
    notice={recruiting ? <CityAdminRecruiting status={recruiting} city={route.scope === 'city' ? route.value ?? '' : ''} /> : undefined}
    initialData={listing?.page ?? undefined} initialSearch={listing?.query}
    onSearch={search => {
      if (!session.siteAnalyticsEnabled || navigator.doNotTrack === '1') return;
      try { navigator.sendBeacon('/api/analytics/event', new Blob([
        JSON.stringify({ event: 'demo_search', resource_id: search.slice(0, 120) }),
      ], { type: 'application/json' })); } catch { /* Optional analytics. */ }
    }} />;
}

/** A quiet invitation where a city has fewer than two active city admins. */
function CityAdminRecruiting({ status, city }: { status: 'none' | 'single'; city: string }) {
  return <aside className="city-admin-recruiting" aria-label="Kaupunkiadminit">
    <p>{status === 'none'
      ? 'Paikkakunnalla ei vielä ole kaupunkiadminia, joka tarkistaisi ilmoitukset. Haluatko auttaa?'
      : 'Paikkakunnalle haetaan toista kaupunkiadminia. Kiinnostaako?'}{' '}
      <a href={`${cityAdminPath}?city=${encodeURIComponent(city)}`}>Hae kaupunkiadminiksi</a></p>
  </aside>;
}
