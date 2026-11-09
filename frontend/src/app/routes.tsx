import type { AppConfig } from './config';
import type { Catalog } from './i18n';
import type { ListingRoute } from './listing';
import { currentMonth } from './calendar';
import { findCity } from './cities';
import { informationPageForPath, informationPages } from './information';
import { contactCopy, contactPath } from './contact-route';
import { campaignCopy, campaignPath } from './campaign-route';
import type { InformationPage } from './information';

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
  | { name: 'submit' }
  | { name: 'god-auth' }
  | { name: 'pride' }
  | { name: 'information'; page: InformationPage }
  | { name: 'contact' }
  | { name: 'campaign' }
  | { name: 'fundraising' }
  | { name: 'cities' }
  | { name: 'calendar' | 'calendar-year'; year: number; month: number; city?: string }
  | { name: 'today'; value?: string }
  | ListingRoute
  | { name: 'organization'; id: string }
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
  const informationPage = informationPageForPath(path);
  if (informationPage) return { name: 'information', page: informationPage };
  if (path === '/auth/god') return { name: 'god-auth' };
  if (path === contactPath) return { name: 'contact' };
  if (path === campaignPath) return { name: 'campaign' };
  if (path === '/keräys' || path === '/ker%C3%A4ys' || path === '/ker%c3%a4ys') return { name: 'fundraising' };
  const calendar = /^\/calendar(?:\/(\d{4})(?:\/(\d{1,2}))?)?\/?$/.exec(path);
  const scoped = /^\/city\/([^/]+)\/calendar(?:\/(\d{4})(?:\/(\d{1,2}))?)?\/?$/.exec(path);
  if (calendar || scoped) {
    const city = scoped ? findCity(readIdentifier(scoped[1]) ?? '') : undefined;
    if (scoped && !city) return null;
    const yearValue = scoped ? scoped[2] : calendar![1];
    const monthValue = scoped ? scoped[3] : calendar![2];
    const current = currentMonth();
    const year = yearValue ? Number(yearValue) : current.year;
    const month = monthValue ? Number(monthValue) : yearValue ? 0 : current.month;
    if (year < 2000 || year > 2100 || month < 0 || month > 12 || monthValue === '0' || monthValue === '00') return null;
    return { name: month ? 'calendar' : 'calendar-year', year, month, ...(city ? { city: city.key } : {}) };
  }
  if (path === '/submit') return { name: 'submit' };
  if (path === '/pride-nakyvaksi' || path === '/pride' || path === '/pride/') return { name: 'pride' };
  if (path === '/cities') return { name: 'cities' };
  if (path === '/mielenosoitukset-tanaan') return { name: 'today' };
  const today = /^\/city\/([^/]+)\/tanaan$/.exec(path);
  if (today) {
    const value = readIdentifier(today[1]);
    return value && !value.includes('/') ? { name: 'today', value } : null;
  }
  const organization = /^\/organization\/([a-f\d]{24})$/i.exec(path);
  if (organization) return { name: 'organization', id: organization[1].toLowerCase() };
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
export function routeMeta(route: AppRoute, config: AppConfig, text: Catalog): RouteMeta {
  if (route.name === 'contact') {
    return { title: `${contactCopy.title} | Mielenosoitukset.fi`, description: contactCopy.description,
      robots: 'index, follow', canonical: config.origin + contactPath };
  }
  if (route.name === 'information') {
    const { path, title, description } = informationPages[route.page];
    return { title: `${title} | Mielenosoitukset.fi`, description,
      robots: 'index, follow', canonical: config.origin + path };
  }
  if (route.name === 'fundraising') {
    return { title: 'Pienkeräys – Mielenosoitukset.fi',
      description: 'Suunnittelemme 2 500 euron pienkeräystä, jotta yhä useampi löytäisi mielenosoitukset.fi-palvelun. Tutustu suunnitelmaan.',
      robots: 'index, follow', canonical: `${config.origin}/ker%C3%A4ys` };
  }
  if (route.name === 'campaign') {
    return { title: campaignCopy.title, description: campaignCopy.description,
      robots: 'index, follow', canonical: config.origin + campaignPath, image: config.origin + campaignCopy.image };
  }
  return {
    title: text.meta.title,
    description: text.meta.description,
    robots: 'index, follow',
    canonical: route.name === 'home' ? `${config.origin}/` : null,
    image: null,
  };
}
