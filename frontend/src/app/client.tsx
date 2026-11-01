import { createRoot } from 'react-dom/client';
import { useEffect, useState } from 'react';
import { App } from './App';
import type { AppConfig } from './config';
import { routeForPath } from './routes';
import type { SessionSummary } from './session';

/**
 * Browser entry for the standalone public app.
 *
 * The server sends metadata and an empty root. Everything visible is rendered
 * here, so a page response costs no React rendering and no event query. Links to
 * routes this app owns are handled without a full document load; every other
 * link keeps normal browser navigation to Flask.
 */

type Bootstrap = { config: AppConfig; session: SessionSummary; path: string };

/** The existing layout scrolls the body element, not only the document. */
function resetScroll() {
  window.scrollTo({ top: 0 });
  document.documentElement.scrollTop = 0;
  document.body.scrollTop = 0;
}

function Root({ config, session, path: initialPath }: Bootstrap) {
  const [path, setPath] = useState(initialPath);
  useEffect(() => {
    function navigate() {
      if (!routeForPath(window.location.pathname)) return;
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
      if (url.origin !== window.location.origin || !routeForPath(url.pathname)) return;
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
  return <App config={config} session={session} route={route} path={path} />;
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
