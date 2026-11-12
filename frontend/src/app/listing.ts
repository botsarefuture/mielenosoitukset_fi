import { cityCatalog, findCity } from './cities';
import type { ListingMessages, ListingProps, Page } from '../components/listings/types';
import type { AppConfig } from './config';
import type { SessionSummary } from './session';
import { ttlCache } from './server-cache';
import { listingQuery as parseQuery } from '../components/listings/query';

export type ListingRoute = { name: 'listing'; scope: 'all' | 'city' | 'tag' | 'organization' | 'today' | 'city-today'; value?: string };
export type CityAdminStatus = 'none' | 'single' | 'team' | 'national';
export type ListingBootstrap = { query: string; page: Page | null; cityAdminStatus?: CityAdminStatus };
const cities = cityCatalog.map(city => city.name);

export function listingFixed(route: ListingRoute): Record<string, string> {
  if (route.scope === 'today') return { today: 'true' };
  if (route.scope === 'city-today') return { today: 'true', city: findCity(route.value!)?.name ?? route.value! };
  if (route.scope === 'organization') return { organization_id: route.value! };
  if (route.scope === 'tag') return { tag: route.value! };
  if (route.scope === 'city') {
    const value = route.value!;
    return { city: findCity(value)?.name ?? `${value.charAt(0).toLocaleUpperCase('fi')}${value.slice(1).toLocaleLowerCase('fi')}` };
  }
  return {};
}

const messages: ListingMessages = {
  search: 'Hae mielenosoituksia', searchPlaceholder: 'Hae mielenosoituksia...', city: 'Kaupunki',
  location: 'Sijainti', startDate: 'Alkupäivä (pp.kk.vvvv)', endDate: 'Loppupäivä (pp.kk.vvvv)',
  dateError: 'Valitse kelvollinen päivämääräväli tulevaisuudesta', year: 'Vuosi', month: 'Kuukausi',
  submitSearch: 'Hae', removeFilter: 'Poista suodatin', loading: 'Ladataan mielenosoituksia...',
  loadMore: 'Näytä lisää', loadingMore: 'Ladataan...', previous: 'Edellinen',
  summary: 'Näytetään __START__–__END__ / __COUNT__ mielenosoituksesta',
  loadError: 'Mielenosoitusten lataaminen epäonnistui. Yritä uudelleen.', retry: 'Yritä uudelleen',
  emptyTitle: 'Ei löytynyt mielenosoituksia', empty: 'Tällä hetkellä ei ole mielenosoituksia. Tarkista myöhemmin.',
  filteredEmpty: 'Kokeile poistaa suodattimia tai hakea toisella sanalla.',
  filters: 'Suodattimet', clearFilters: 'Poista suodattimet', submitEvent: 'Ilmoita uusi mielenosoitus', cancelled: 'Peruttu', today: 'Tänään',
  startingFrom: 'alkaen', endTime: 'Päättymisaika', loginPrompt: 'Kirjaudu sisään käyttääksesi sosiaalisia toimintoja',
  attendingSuffix: 'osallistuu', loadingFriends: 'Ladataan kavereita...', invite: 'Kutsu kavereita',
  allEvents: 'Kaikki mielenosoitukset',
};

export function listingProps(route: ListingRoute, config: AppConfig, session: SessionSummary): ListingProps {
  const fixed = listingFixed(route);
  const today = route.scope === 'today' || route.scope === 'city-today';
  const title = today ? `Mielenosoitukset ${route.scope === 'city-today' ? findCity(route.value!)?.phrase ?? fixed.city : 'Suomessa'} tänään`
    : route.scope === 'tag' ? `#${route.value}: Mielenosoitukset`
    : route.scope === 'city' ? `${fixed.city}: Mielenosoitukset`
      : route.scope === 'organization' ? 'Mielenosoitukset' : 'Tulevat mielenosoitukset';
  const feed = new URLSearchParams(fixed).toString();
  return {
    title, locale: config.locale, fixed, cities, authenticated: session.authenticated,
    endpoint: `${config.apiBase}/demonstrations`, attendanceEndpoint: config.urls.attendance,
    allEventsUrl: config.urls.demonstrations, submitUrl: config.urls.submit,
    rssUrl: route.scope === 'organization' || today ? null : `${config.urls.rss}${feed ? `?${feed}` : ''}`,
    calendarUrl: (route.scope === 'city' || route.scope === 'city-today') && findCity(route.value!)
      ? `/city/${findCity(route.value!)!.key}/calendar/` : route.scope === 'all' || route.scope === 'today' ? '/calendar/' : undefined,
    headingLevel: route.scope === 'organization' ? 2 : 1,
    detailUrl: config.urls.detail, seriesUrl: config.urls.series, tagUrl: config.urls.tag,
    cover: null, coverAlt: 'Tagin kansikuva',
    messages: { ...messages, ...(route.scope === 'tag' ? { empty: 'Tällä tagilla ei ole näkyvillä olevia mielenosoituksia.' } : {}),
      ...(today ? { emptyTitle: 'Ei mielenosoituksia tänään', empty: 'Tälle päivälle ei ole ilmoitettu mielenosoituksia. Katso myös tulevat tapahtumat.' } : {}),
      ...(route.scope === 'organization' ? { emptyTitle: 'Ei tulevia mielenosoituksia',
        empty: 'Tämä järjestäjä ei ole vielä ilmoittanut tulevia mielenosoituksia.' } : {}) },
  };
}

export function listingQuery(route: ListingRoute, search: string, locale: string): string {
  const { params, page } = parseQuery(search, listingFixed(route));
  const query = new URLSearchParams(Object.entries({ ...params, page }).map(([key, value]) => [key, String(value)]));
  query.set('lang', locale);
  query.sort();
  return query.toString();
}

export function validListingPage(value: unknown): value is Page {
  if (!value || typeof value !== 'object') return false;
  const data = value as Page;
  return Number.isSafeInteger(data.page) && data.page >= 1
    && Number.isSafeInteger(data.per_page) && data.per_page >= 1 && data.per_page <= 100
    && Number.isSafeInteger(data.total) && data.total >= 0
    && Number.isSafeInteger(data.total_pages) && data.total_pages >= 1
    && Number.isSafeInteger(data.result_start) && Number.isSafeInteger(data.result_end)
    && Array.isArray(data.results) && data.results.length <= data.per_page
    && data.results.every(row => row && typeof row._id === 'string' && typeof row.title === 'string');
}

const pages = ttlCache<Page>(30_000, 64);
const pending = new Map<string, Promise<Page | null>>();

/** Successful public batches only; private header state never enters this cache. */
/** Whether a city still needs city admins. Only the coverage band is public. */
export async function loadCityAdminStatus(readBase: string, cityKey: string): Promise<CityAdminStatus | undefined> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 800);
  try {
    const response = await fetch(`${readBase}/cities/${encodeURIComponent(cityKey)}/admin-status`, {
      signal: controller.signal, credentials: 'omit', headers: { Accept: 'application/json' },
    });
    if (!response.ok) return undefined;
    const status = (await response.json() as { status?: unknown }).status;
    return status === 'none' || status === 'single' || status === 'team' || status === 'national' ? status : undefined;
  } catch {
    return undefined;
  } finally {
    clearTimeout(timer);
  }
}

export async function loadListingPage(readBase: string, query: string): Promise<Page | null> {
  if (query.length > 4096) return null;
  const day = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Helsinki' }).format(new Date());
  const key = `${readBase}\n${day}\n${query}`;
  const cached = pages.get(key);
  if (cached) return cached;
  if (pending.has(key)) return pending.get(key)!;
  // Do not grow an unbounded queue of arbitrary search combinations.
  if (pending.size >= 16) return null;
  const promise = (async () => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 1200);
    try {
      const response = await fetch(`${readBase}/demonstrations?${query}`, {
        signal: controller.signal, credentials: 'omit', headers: { Accept: 'application/json' },
      });
      if (!response.ok) return null;
      const data: unknown = await response.json();
      if (!validListingPage(data)) return null;
      if (!/no-store/i.test(response.headers.get('Cache-Control') ?? '')) pages.set(key, data);
      return data;
    } catch { return null; }
    finally { clearTimeout(timer); }
  })().finally(() => pending.delete(key));
  pending.set(key, promise);
  return promise;
}
