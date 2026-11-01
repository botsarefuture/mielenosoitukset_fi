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
      jsonLd: Record<string, unknown>; heading: string }
  | { status: 'not-found' }
  | { status: 'unavailable' };

type Payload = {
  id: string;
  title: string;
  description: string | null;
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
  return {
    id,
    title,
    description: text(data.description),
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
