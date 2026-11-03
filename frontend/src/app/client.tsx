import { createRoot } from 'react-dom/client';
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
      if (!name || !['home', 'listing', 'organization', 'cities', 'today', 'submit', 'calendar'].includes(name)
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
    createRoot(container).render(<Root {...(JSON.parse(bootstrap) as Bootstrap)} />);
  } catch (error) {
    console.error('Could not start the public app', error);
    container.textContent = 'Mielenosoitukset.fi · /demonstrations';
  }
}
