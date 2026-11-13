import { createRoot, hydrateRoot } from 'react-dom/client';
import { useEffect, useRef } from 'react';
import { App } from './App';
import type { AppProps } from './App';
import { routeForPath } from './routes';

type Bootstrap = Omit<AppProps, 'route'>;

/** Normal document navigation owns routes, metadata and browser history.
 * React owns in-page search, filters and pagination. No home-only navigation
 * interception: every page gets its matching server head and public bootstrap.
 */
function Root(props: Bootstrap) {
  const tracked = useRef(false);
  const { path, session } = props;
  useEffect(() => {
    function activate() {
      if ((document as Document & { prerendering?: boolean }).prerendering || navigator.doNotTrack === '1') return;
      if (session.matomoEnabled && !document.getElementById('public-app-matomo')) {
        const script = document.createElement('script');
        script.id = 'public-app-matomo'; script.src = '/static/js/matomo.js'; script.async = true;
        document.head.appendChild(script);
      }
      // Detail/series views keep their separate demonstration-view collection.
      const name = routeForPath(path)?.name;
      if (!name || !['home', 'listing', 'organization', 'cities', 'today', 'submit', 'calendar', 'calendar-year', 'pride', 'information', 'campaign', 'fundraising', 'contact', 'city-admin', 'organization-fill', 'suggest-change', 'api-docs'].includes(name)
        || !session.siteAnalyticsEnabled || tracked.current) return;
      tracked.current = true;
      try {
        navigator.sendBeacon('/api/analytics/pageview', new Blob([
          JSON.stringify({ referrer: document.referrer }),
        ], { type: 'application/json' }));
      } catch { /* Optional analytics. */ }
    }
    activate();
    document.addEventListener('prerenderingchange', activate);
    return () => document.removeEventListener('prerenderingchange', activate);
  }, [path, session.siteAnalyticsEnabled, session.matomoEnabled]);
  const route = routeForPath(path);
  return route ? <App {...props} route={route} /> : null;
}

const container = document.getElementById('app');
const bootstrap = document.getElementById('app-bootstrap')?.textContent;
if (container) {
  try {
    if (!bootstrap) throw new Error('Missing app bootstrap');
    const props = JSON.parse(bootstrap) as Bootstrap;
    const route = routeForPath(props.path);
    if (route?.name === 'api-docs') {
      const html = document.getElementById('api-docs-page')?.innerHTML;
      if (!html) throw new Error('Missing API documentation');
      hydrateRoot(container, <Root {...props} serverPage={<div id="api-docs-page" dangerouslySetInnerHTML={{ __html: html }} />} />);
    } else if (route?.name === 'status') {
      void import('./StatusScreen').then(({ default: StatusScreen }) => {
        hydrateRoot(container, <Root {...props} serverPage={<StatusScreen status={props.serviceStatus ?? null} />} />);
      }).catch(error => console.error('Could not start the status page', error));
    } else if (route?.name === 'information') {
      void import('./InformationScreen').then(({ default: InformationScreen }) => {
        hydrateRoot(container, <Root {...props} serverPage={<InformationScreen page={route.page} session={props.session} campaign={props.campaignVisible} />} />);
      }).catch(error => console.error('Could not start information page controls', error));
    } else if (route?.name === 'suggest-change' && props.suggestionDemo) {
      const demo = props.suggestionDemo;
      void import('./SuggestChangeScreen').then(({ default: SuggestChangeScreen }) => {
        hydrateRoot(container, <Root {...props} serverPage={<SuggestChangeScreen demo={demo} />} />);
      });
    } else if (route?.name === 'cancel-link' && props.cancelLink) {
      const link = props.cancelLink;
      const token = route.token;
      void import('./CancelLinkScreen').then(({ default: CancelLinkScreen }) => {
        hydrateRoot(container, <Root {...props} serverPage={<CancelLinkScreen link={link} token={token} />} />);
      }).catch(error => console.error('Could not start the cancellation page', error));
    } else if (route?.name === 'developer') {
      const appId = route.appId;
      void import('./DeveloperScreen').then(({ default: DeveloperScreen }) => {
        hydrateRoot(container, <Root {...props} serverPage={<DeveloperScreen config={props.config} session={props.session} appId={appId} />} />);
      }).catch(error => console.error('Could not start the developer panel', error));
    } else if (route?.name === 'organization-fill' && props.organizationFill) {
      const profile = props.organizationFill;
      void import('./OrganizationFillScreen').then(({ default: OrganizationFillScreen }) => {
        hydrateRoot(container, <Root {...props} serverPage={<OrganizationFillScreen profile={profile} />} />);
      }).catch(error => console.error('Could not start the organization fill-in form', error));
    } else if (route?.name === 'city-admin') {
      void import('./CityAdminApplyScreen').then(({ default: CityAdminApplyScreen }) => {
        hydrateRoot(container, <Root {...props} serverPage={<CityAdminApplyScreen session={props.session} apiBase={props.config.apiBase} />} />);
      }).catch(error => console.error('Could not start the city admin application page', error));
    } else if (route?.name === 'contact') {
      void import('./ContactScreen').then(({ default: ContactScreen }) => {
        hydrateRoot(container, <Root {...props} serverPage={<ContactScreen session={props.session} />} />);
      }).catch(error => console.error('Could not start the contact page', error));
    } else if (route?.name === 'fundraising') {
      void import('./FundraisingScreen').then(({ default: FundraisingScreen }) => {
        hydrateRoot(container, <Root {...props} serverPage={<FundraisingScreen config={props.config} today={props.today ?? ''} data={props.fundraising} />} />);
      }).catch(error => console.error('Could not start the fundraising page', error));
    } else if (route?.name === 'campaign') {
      void import('./CampaignScreen').then(({ default: CampaignScreen }) => {
        hydrateRoot(container, <Root {...props} serverPage={<CampaignScreen config={props.config} />} />);
      }).catch(error => console.error('Could not start campaign page forms', error));
    } else {
      createRoot(container).render(<Root {...props} />);
    }
  } catch (error) {
    console.error('Could not start the public app', error);
    container.textContent = 'Mielenosoitukset.fi · /demonstrations';
  }
}
