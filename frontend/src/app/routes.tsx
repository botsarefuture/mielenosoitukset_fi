import type { AppConfig } from './config';
import type { Catalog } from './i18n';

/**
 * Public routes owned by the standalone React application.
 *
 * Only routes listed here are served by the React host. Everything else keeps
 * its existing Flask handler, so an unknown path is never claimed here.
 */
export type AppRoute = { name: 'home' };

export type RouteMeta = {
  title: string;
  description: string;
  robots: string;
  canonical: string | null;
};

export function routeForPath(path: string): AppRoute | null {
  const clean = path.replace(/\/+$/, '') || '/';
  if (clean === '/') return { name: 'home' };
  return null;
}

/**
 * Metadata is the only part of the page rendered on the server. It needs no
 * event request for this route, so a page response never waits for the database.
 */
export function routeMeta(_route: AppRoute, _config: AppConfig, text: Catalog): RouteMeta {
  return {
    title: text.meta.title,
    description: text.meta.description,
    robots: 'index, follow',
    canonical: null,
  };
}
