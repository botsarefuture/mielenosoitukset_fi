import type { AppConfig } from './config';
import type { Catalog } from './i18n';

/**
 * Public routes owned by the standalone React application.
 *
 * Only routes listed here are served by the React host. Everything else keeps
 * its existing Flask handler, so an unknown path is never claimed here. The
 * detail route claims exactly one path segment: `/demonstration/<id>/ics`,
 * `/demonstration/<id>/children` and a trailing slash all stay on Flask.
 */
export type AppRoute = { name: 'home' } | { name: 'detail'; identifier: string };

export type RouteMeta = {
  title: string;
  description: string;
  robots: string;
  canonical: string | null;
  /** Social preview image; the default site image when absent. */
  image?: string | null;
};

const DETAIL_PATH = /^\/demonstration\/([^/]+)$/;

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
