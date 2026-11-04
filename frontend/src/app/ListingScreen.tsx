import { PublicListingPage } from '../pages/PublicListingPage';
import type { AppConfig } from './config';
import { listingProps } from './listing';
import type { ListingBootstrap, ListingRoute } from './listing';
import type { SessionSummary } from './session';

/** Keep listing filters, calendar and city data off the home-page load path. */
export default function ListingScreen({ route, config, session, listing }: {
  route: ListingRoute; config: AppConfig; session: SessionSummary; listing?: ListingBootstrap;
}) {
  return <PublicListingPage {...listingProps(route, config, session)}
    initialData={listing?.page ?? undefined} initialSearch={listing?.query}
    onSearch={search => {
      if (!session.siteAnalyticsEnabled || navigator.doNotTrack === '1') return;
      try { navigator.sendBeacon('/api/analytics/event', new Blob([
        JSON.stringify({ event: 'demo_search', resource_id: search.slice(0, 120) }),
      ], { type: 'application/json' })); } catch { /* Optional analytics. */ }
    }} />;
}
