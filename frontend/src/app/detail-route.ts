import type { AppConfig } from './config';
import { detailPath } from './detail';
import type { RouteMeta } from './routes';
import { ttlCache } from './server-cache';

/**
 * Server-side metadata for one public event.
 *
 * The head is the only indexed part of the detail page, so it needs the event
 * once before the first byte. This is a single projected read from the existing
 * public API; the page body is still fetched by the browser. Nothing here
 * decides permissions: visibility is the API's answer, and a missing event is a
 * missing event.
 */

/** Finnish msgids that the Flask shell uses when the event has no value. */
const FALLBACK_TITLE = 'Mielenosoitus';
const FALLBACK_DESCRIPTION = 'Mielenosoituksen tiedot.';

/** Same rule as the Flask shell: dates past the discovery horizon stay noindex. */
const NOINDEX_HORIZON_DAYS = 365 * 2;
const HEAD_TIMEOUT_MS = 1500;
const DESCRIPTION_LIMIT = 200;
/** Repeat renders of the same event reuse the head instead of re-reading it. */
const HEAD_CACHE_TTL_MS = 60_000;
const HEAD_CACHE_ENTRIES = 500;

export type DetailBootstrap = {
  /** Resolved public id; the browser component only accepts this form. */
  id: string;
  identifier: string;
  canonicalUrl: string;
};

export type DetailLoad =
  | { status: 'ready'; meta: RouteMeta; bootstrap: DetailBootstrap; noindex: boolean;
      jsonLd: Record<string, unknown>; heading: string;
      /** Present when the event belongs to a recurring series. */
      parent: string | null; slug: string | null; occurrence: SeriesOccurrence }
  | { status: 'not-found' }
  | { status: 'unavailable' };

export type SeriesOccurrence = {
  id: string;
  slug: string | null;
  runningNumber: number | null;
  date: string | null;
  startTime: string | null;
  endTime: string | null;
  cancelled: boolean;
};

export type SeriesLoad =
  | { status: 'ready'; parent: string; occurrences: SeriesOccurrence[]; indexable: boolean }
  | { status: 'not-found' }
  | { status: 'unavailable' };

/** One occurrence as the series navigation renders it. */
export type DetailSeries = {
  title: string;
  occurrences: { id: string; url: string; date: string; start_time: string | null;
    end_time: string | null; cancelled: boolean; selected: boolean }[];
};

type Payload = {
  id: string;
  title: string;
  description: string | null;
  parent: string | null;
  slug: string | null;
  runningNumber: number | null;
  date: string | null;
  startTime: string | null;
  endTime: string | null;
  cancelled: boolean;
  city: string | null;
  address: string | null;
  previewImage: string | null;
};

const text = (value: unknown): string | null => {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
};

const count = (value: unknown): number | null =>
  typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : null;

/** Plain text for meta descriptions and structured data, like Jinja's striptags. */
export function plainText(value: unknown): string {
  if (typeof value !== 'string') return '';
  return value
    .replace(/<[^>]*>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Jinja's `truncate(200, true)`: the ellipsis counts towards the limit. */
export function truncate(value: string, limit = DESCRIPTION_LIMIT): string {
  return value.length > limit ? `${value.slice(0, limit - 3).trimEnd()}...` : value;
}

function isoDay(offsetDays = 0): string {
  const formatter = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Helsinki' });
  const today = formatter.format(new Date());
  if (!offsetDays) return today;
  const base = Date.parse(`${today}T12:00:00Z`);
  return new Date(base + offsetDays * 86_400_000).toISOString().slice(0, 10);
}

function beyondHorizon(date: string | null): boolean {
  if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) return false;
  return date > isoDay(NOINDEX_HORIZON_DAYS);
}

function absolute(config: AppConfig, value: string | null): string | null {
  if (!value) return null;
  if (/^https?:\/\//i.test(value)) return value;
  if (value.startsWith('//')) return null;
  if (value.startsWith('/')) return `${config.origin}${value}`;
  return null;
}

export function parseDetailPayload(value: unknown): Payload | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const data = value as Record<string, unknown>;
  const id = typeof data._id === 'string' && /^[a-f\d]{24}$/i.test(data._id) ? data._id : null;
  const title = text(data.title);
  if (!id || !title) return null;
  const date = text(data.date);
  const parent = typeof data.parent === 'string' && /^[a-f\d]{24}$/i.test(data.parent) ? data.parent : null;
  return {
    id,
    title,
    description: text(data.description),
    parent,
    slug: text(data.slug),
    runningNumber: count(data.running_number),
    date: date && /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : null,
    startTime: text(data.start_time),
    endTime: text(data.end_time),
    cancelled: data.cancelled === true,
    city: text(data.city),
    address: text(data.address),
    previewImage: text(data.preview_image),
  };
}

/** Canonical public identifier: the same precedence the site already uses. */
function canonicalIdentifier(payload: Payload): string {
  return payload.slug ?? (payload.runningNumber === null ? null : String(payload.runningNumber)) ?? payload.id;
}

function jsonLd(config: AppConfig, payload: Payload, canonical: string, description: string) {
  const day = payload.date ?? '';
  return {
    '@context': 'https://schema.org',
    '@type': 'Event',
    name: payload.title,
    description,
    url: canonical,
    startDate: `${day}T${payload.startTime ?? '00:00:00'}`,
    endDate: `${day}T${payload.endTime ?? '23:59:00'}`,
    eventStatus: payload.cancelled
      ? 'https://schema.org/EventCancelled'
      : 'https://schema.org/EventScheduled',
    eventAttendanceMode: 'https://schema.org/OfflineEventAttendanceMode',
    location: {
      '@type': 'Place',
      name: payload.address ?? payload.city ?? '',
      address: {
        '@type': 'PostalAddress',
        streetAddress: payload.address ?? '',
        addressLocality: payload.city ?? '',
        addressCountry: 'FI',
      },
    },
  };
}

/**
 * Read one event from the public API. The request is bounded and never cached
 * here: the API sets the cache policy that applies to the document.
 */
export async function loadDetail(
  identifier: string,
  config: AppConfig,
  apiBase: string = config.apiBase,
  fetchImpl: typeof fetch = fetch,
): Promise<DetailLoad> {
  const url = `${apiBase}/demonstrations/${encodeURIComponent(identifier)}?lang=${encodeURIComponent(config.locale)}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), HEAD_TIMEOUT_MS);
  try {
    const response = await fetchImpl(url, {
      signal: controller.signal,
      credentials: 'omit',
      headers: { Accept: 'application/json' },
    });
    // An unsupported identifier and an unknown event are the same answer here.
    if (response.status === 400 || response.status === 404) return { status: 'not-found' };
    if (!response.ok) return { status: 'unavailable' };
    const payload = parseDetailPayload(await response.json());
    if (!payload) return { status: 'not-found' };

    const canonical = `${config.origin}${detailPath(config, canonicalIdentifier(payload))}`;
    const description = truncate(plainText(payload.description)) || FALLBACK_DESCRIPTION;
    const noindex = beyondHorizon(payload.date);
    return {
      status: 'ready',
      noindex,
      heading: payload.title,
      bootstrap: { id: payload.id, identifier, canonicalUrl: canonical },
      meta: {
        title: `${payload.title || FALLBACK_TITLE} | Mielenosoitukset.fi`,
        description,
        robots: noindex ? 'noindex, follow' : 'index, follow',
        canonical,
        image: absolute(config, payload.previewImage) ?? `${config.origin}/screenshot/${payload.id}`,
      },
      jsonLd: jsonLd(config, payload, canonical, plainText(payload.description) || FALLBACK_DESCRIPTION),
      parent: payload.parent,
      slug: payload.slug,
      occurrence: {
        id: payload.id, slug: payload.slug, runningNumber: payload.runningNumber,
        date: payload.date, startTime: payload.startTime, endTime: payload.endTime,
        cancelled: payload.cancelled,
      },
    };
  } catch {
    return { status: 'unavailable' };
  } finally {
    clearTimeout(timer);
  }
}

const heads = ttlCache<Extract<DetailLoad, { status: 'ready' }>>(HEAD_CACHE_TTL_MS, HEAD_CACHE_ENTRIES);

/**
 * Cached head read. Only successful public metadata is stored, so a published
 * event appears immediately while repeat page views cost no API request.
 */
export async function loadDetailHead(
  identifier: string,
  config: AppConfig,
  apiBase: string = config.apiBase,
): Promise<DetailLoad> {
  const key = `${apiBase}\n${config.locale}\n${identifier}`;
  const cached = heads.get(key);
  if (cached) return cached;
  const loaded = await loadDetail(identifier, config, apiBase);
  if (loaded.status === 'ready') heads.set(key, loaded);
  return loaded;
}

/** Series membership changes when occurrences are generated, so the TTL is short. */
const SERIES_CACHE_TTL_MS = 30_000;
const SERIES_CACHE_ENTRIES = 200;
const seriesCache = ttlCache<Extract<SeriesLoad, { status: 'ready' }>>(SERIES_CACHE_TTL_MS, SERIES_CACHE_ENTRIES);

/** Public series path, matching the existing `/children` route. */
export function seriesPath(config: AppConfig, parent: string, occurrence?: string | null): string {
  const path = config.urls.series.replace('__ID__', encodeURIComponent(parent));
  return occurrence ? `${path}?occurrence=${encodeURIComponent(occurrence)}` : path;
}

/** Current wall clock in Helsinki as `YYYY-MM-DDTHH:MM:SS`, comparable to dates. */
export function helsinkiNow(now = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Europe/Helsinki', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  }).formatToParts(now);
  const value = (type: string) => parts.find((part) => part.type === type)?.value ?? '00';
  return `${value('year')}-${value('month')}-${value('day')}T${value('hour')}:${value('minute')}:${value('second')}`;
}

function clock(value: string | null, fallback: string): string {
  if (!value) return fallback;
  const match = /^(\d{1,2}):(\d{2})(?::(\d{2}))?/.exec(value.trim());
  if (!match) return fallback;
  const pad = (part: string | undefined) => (part ?? '00').padStart(2, '0');
  return `${pad(match[1])}:${pad(match[2])}:${pad(match[3])}`;
}

/** End instant of one occurrence, in the same local form the clock returns. */
function occurrenceEnd(occurrence: SeriesOccurrence): string | null {
  if (!occurrence.date) return null;
  return `${occurrence.date}T${clock(occurrence.endTime ?? occurrence.startTime, '23:59:59')}`;
}

function occurrenceOrder(occurrence: SeriesOccurrence): string {
  return `${occurrence.date ?? ''}|${occurrence.startTime ? '0' : '1'}|${clock(occurrence.startTime, '00:00:00')}|${occurrence.id}`;
}

/**
 * The occurrence the series page opens with: the next active one, otherwise the
 * latest past one, matching the Flask chooser. A requested slug, id or running
 * number wins, including a cancelled occurrence explicitly requested by URL.
 */
export function selectOccurrence(
  occurrences: SeriesOccurrence[],
  requested: string | null,
  now = helsinkiNow(),
): SeriesOccurrence | null {
  const wanted = requested?.trim();
  if (wanted) {
    const match = occurrences.find((occurrence) => occurrence.slug === wanted || occurrence.id === wanted
      || (occurrence.runningNumber !== null && String(occurrence.runningNumber) === wanted));
    if (match) return match;
  }
  const active = occurrences
    .filter((occurrence) => !occurrence.cancelled && occurrenceEnd(occurrence) !== null)
    .sort((left, right) => occurrenceOrder(left).localeCompare(occurrenceOrder(right)));
  if (!active.length) return null;
  const next = active.find((occurrence) => (occurrenceEnd(occurrence) ?? '') >= now);
  return next ?? active[active.length - 1];
}

function parseOccurrence(value: unknown): SeriesOccurrence | null {
  if (!value || typeof value !== 'object') return null;
  const data = value as Record<string, unknown>;
  if (typeof data.id !== 'string' || !/^[a-f\d]{24}$/i.test(data.id)) return null;
  const date = text(data.date);
  const running = count(data.running_number);
  return {
    id: data.id,
    slug: text(data.slug),
    runningNumber: running,
    date: date && /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : null,
    startTime: text(data.start_time),
    endTime: text(data.end_time),
    cancelled: data.cancelled === true,
  };
}

/** Read one series and cache it briefly; only a public series is stored. */
export async function loadSeries(
  parent: string,
  config: AppConfig,
  apiBase: string = config.apiBase,
): Promise<SeriesLoad> {
  const key = `${apiBase}\n${config.locale}\n${parent}`;
  const cached = seriesCache.get(key);
  if (cached) return cached;
  const url = `${apiBase}/series/${encodeURIComponent(parent)}?lang=${encodeURIComponent(config.locale)}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), HEAD_TIMEOUT_MS);
  try {
    const response = await fetch(url, {
      signal: controller.signal, credentials: 'omit', headers: { Accept: 'application/json' },
    });
    if (response.status === 400 || response.status === 404) return { status: 'not-found' };
    if (!response.ok) return { status: 'unavailable' };
    const body = (await response.json()) as Record<string, unknown>;
    if (!Array.isArray(body.occurrences)) return { status: 'not-found' };
    const occurrences = body.occurrences
      .map(parseOccurrence)
      .filter((entry): entry is SeriesOccurrence => entry !== null);
    const windowStart = isoDay(-365);
    const windowEnd = isoDay(NOINDEX_HORIZON_DAYS);
    const loaded = {
      status: 'ready' as const,
      parent,
      occurrences,
      indexable: occurrences.some((occurrence) => !occurrence.cancelled && occurrence.date !== null
        && occurrence.date >= windowStart && occurrence.date <= windowEnd),
    };
    seriesCache.set(key, loaded);
    return loaded;
  } catch {
    return { status: 'unavailable' };
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Navigation items for the series: upcoming occurrences first, then past and
 * cancelled ones, the same order the chooser page lists them in.
 */
export function seriesNavigation(
  config: AppConfig,
  series: Extract<SeriesLoad, { status: 'ready' }>,
  selectedId: string,
  title: string,
): DetailSeries {
  const now = helsinkiNow();
  const dated = series.occurrences.filter((occurrence) => occurrence.date !== null);
  const upcoming = dated
    .filter((occurrence) => !occurrence.cancelled && (occurrenceEnd(occurrence) ?? '') >= now)
    .sort((left, right) => occurrenceOrder(left).localeCompare(occurrenceOrder(right)));
  const past = dated
    .filter((occurrence) => occurrence.cancelled || (occurrenceEnd(occurrence) ?? '') < now)
    .sort((left, right) => occurrenceOrder(right).localeCompare(occurrenceOrder(left)));
  return {
    title,
    occurrences: [...upcoming, ...past].map((occurrence) => ({
      id: occurrence.id,
      url: seriesPath(config, series.parent, occurrence.slug ?? occurrence.id),
      date: occurrence.date as string,
      start_time: occurrence.startTime,
      end_time: occurrence.endTime,
      cancelled: occurrence.cancelled,
      selected: occurrence.id === selectedId,
    })),
  };
}
