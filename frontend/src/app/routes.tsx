import type { AppConfig } from './config';
import type { Catalog } from './i18n';
import type { ListingRoute } from './listing';

/**
 * Public routes owned by the standalone React application.
 *
 * Only routes listed here are served by the React host. Everything else keeps
 * its existing Flask handler, so an unknown path is never claimed here. The
 * detail route claims exactly one path segment and the series route claims the
 * `/children` path; `/demonstration/<id>/ics`, `/demonstration/<id>/some` and a
 * trailing slash all stay on Flask.
 */
export type AppRoute =
  | { name: 'home' }
  | ListingRoute
  | { name: 'detail'; identifier: string }
  | { name: 'series'; parent: string };

export type RouteMeta = {
  title: string;
  description: string;
  robots: string;
  canonical: string | null;
  /** Social preview image; the default site image when absent. */
  image?: string | null;
};

const DETAIL_PATH = /^\/demonstration\/([^/]+)$/;
const SERIES_PATH = /^\/demonstration\/([^/]+)\/children$/;

function readIdentifier(raw: string): string | null {
  try {
    const identifier = decodeURIComponent(raw);
    // The API caps resolution at 200 characters; reject anything that cannot be
    // an identifier before the host makes a request.
    if (!identifier || identifier.length > 200) return null;
    if (/[\u0000-\u001f\u007f]/.test(identifier)) return null;
    return identifier;
  } catch {
    return null;
  }
}

export function routeForPath(path: string): AppRoute | null {
  if (path === '/demonstrations') return { name: 'listing', scope: 'all' };
  const listing = /^\/(city|tag)\/([^/]+)$/.exec(path);
  if (listing) {
    const value = readIdentifier(listing[2]);
    return value && !value.includes('/') ? { name: 'listing', scope: listing[1] as 'city' | 'tag', value } : null;
  }
  const series = SERIES_PATH.exec(path);
  if (series) {
    const parent = readIdentifier(series[1]);
    return parent && /^[a-f\d]{24}$/i.test(parent) ? { name: 'series', parent } : null;
  }
  const match = DETAIL_PATH.exec(path);
  if (match) {
    const identifier = readIdentifier(match[1]);
    return identifier ? { name: 'detail', identifier } : null;
  }
  const clean = path.replace(/\/+$/, '') || '/';
  if (clean === '/') return { name: 'home' };
  return null;
}

/**
 * Metadata is the only part of the page rendered on the server. The home route
 * needs no event request; its head is static. The detail route supplies its own
 * metadata from one projected API read.
 */
export function routeMeta(_route: AppRoute, _config: AppConfig, text: Catalog): RouteMeta {
  return {
    title: text.meta.title,
    description: text.meta.description,
    robots: 'index, follow',
    canonical: null,
    image: null,
  };
}
