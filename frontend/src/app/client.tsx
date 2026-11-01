import { createRoot } from 'react-dom/client';
import { useEffect, useRef, useState } from 'react';
import { App } from './App';
import type { AppConfig } from './config';
import type { DetailBootstrap, DetailSeries } from './detail-route';
import type { HomeData } from '../pages/HomePage';
import { routeForPath } from './routes';
import type { AppRoute } from './routes';
import type { SessionSummary } from './session';

/**
 * Browser entry for the standalone public app.
 *
 * The server sends metadata and an empty root. Everything visible is rendered
 * here, so a page response costs no React rendering and no event query. Links to
 * routes this app owns are handled without a full document load; every other
 * link keeps normal browser navigation to Flask.
 */

type Bootstrap = { config: AppConfig; session: SessionSummary; path: string;
  detail?: DetailBootstrap; series?: DetailSeries; home?: HomeData | null };

/**
 * Routes the app can enter without a server round trip for their metadata.
 * A detail page is always loaded as a document, so its head, canonical URL and
 * resolved event id come from the server; only the front page navigates in place.
 */
function clientRoute(path: string): AppRoute | null {
  const route = routeForPath(path);
  return route?.name === 'home' ? route : null;
}

/** The existing layout scrolls the body element, not only the document. */
function resetScroll() {
  window.scrollTo({ top: 0 });
  document.documentElement.scrollTop = 0;
  document.body.scrollTop = 0;
}

function Root({ config, session, path: initialPath, detail, series, home }: Bootstrap) {
  const [path, setPath] = useState(initialPath);
  const trackedPage = useRef<string | null>(null);
  useEffect(() => {
    function activate() {
      // Detail views are counted by the screen's own track_view call, so the
      // generic pageview beacon must not misattribute them to the referrer.
      if ((document as Document & { prerendering?: boolean }).prerendering
        || navigator.doNotTrack === '1' || !clientRoute(path)) return;
      if (session.matomoEnabled && !document.getElementById('public-app-matomo')) {
        const script = document.createElement('script');
        script.id = 'public-app-matomo';
        script.src = '/static/js/matomo.js';
        script.async = true;
        document.head.appendChild(script);
      }
      if (!session.siteAnalyticsEnabled || trackedPage.current === path) return;
      trackedPage.current = path;
      try {
        navigator.sendBeacon('/api/analytics/pageview', new Blob([
          JSON.stringify({ referrer: document.referrer }),
        ], { type: 'application/json' }));
      } catch { /* Optional analytics never blocks rendering or navigation. */ }
    }
    activate();
    document.addEventListener('prerenderingchange', activate);
    return () => document.removeEventListener('prerenderingchange', activate);
  }, [path, session.siteAnalyticsEnabled, session.matomoEnabled]);
  useEffect(() => {
    function navigate() {
      if (!clientRoute(window.location.pathname)) return;
      setPath(window.location.pathname);
      resetScroll();
    }
    function onClick(event: MouseEvent) {
      if (event.defaultPrevented || event.button !== 0
        || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const anchor = (event.target as Element | null)?.closest('a');
      if (!anchor) return;
      const target = anchor.getAttribute('target');
      if (target && target !== '_self') return;
      if (anchor.hasAttribute('download')) return;
      const href = anchor.getAttribute('href');
      if (!href || href.startsWith('#')) return;
      let url: URL;
      try { url = new URL(href, window.location.origin); } catch { return; }
      if (url.origin !== window.location.origin || !clientRoute(url.pathname)) return;
      event.preventDefault();
      window.history.pushState({ appPath: url.pathname }, '', url);
      setPath(url.pathname);
      resetScroll();
    }
    document.addEventListener('click', onClick);
    window.addEventListener('popstate', navigate);
    return () => {
      document.removeEventListener('click', onClick);
      window.removeEventListener('popstate', navigate);
    };
  }, []);
  const route = routeForPath(path);
  if (!route) return null;
  return <App config={config} session={session} route={route} path={path} detail={detail} series={series} home={home} />;
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
