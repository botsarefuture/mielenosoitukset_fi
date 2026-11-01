import type { AppLocale } from './config';
import { isLocale } from './config';

/**
 * Header state for the public app.
 *
 * Flask owns the session and permissions. This summary is the only account data
 * the React host receives: no cookie value, token or private field is included.
 */
export type SessionSummary = {
  authenticated: boolean;
  locale: AppLocale;
  /** Public locales enabled by the server configuration. */
  locales: { code: AppLocale; name: string }[];
  role: string;
  name: string | null;
  picture: string | null;
  globalAdmin: boolean;
  hasAdminAccess: boolean;
  unread: number;
  fundraising: boolean;
  siteAnalyticsEnabled: boolean;
  matomoEnabled: boolean;
};

export const anonymousSession: SessionSummary = {
  authenticated: false, locale: 'fi', locales: [{ code: 'fi', name: 'Suomi' }],
  role: 'guest', name: null, picture: null,
  globalAdmin: false, hasAdminAccess: false, unread: 0, fundraising: false,
  siteAnalyticsEnabled: false, matomoEnabled: false,
};

/** Reject anything that does not match the agreed endpoint contract. */
export function normalizeSession(value: unknown): SessionSummary {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return { ...anonymousSession };
  const raw = value as Record<string, unknown>;
  const locales = Array.isArray(raw.locales)
    ? raw.locales.flatMap((item) => {
      const entry = item as { code?: unknown; name?: unknown } | null;
      if (!entry || !isLocale(entry.code)) return [];
      const name = typeof entry.name === 'string' && entry.name ? entry.name.slice(0, 60) : entry.code;
      return [{ code: entry.code, name }];
    })
    : [];
  const enabled = locales.length ? locales : [{ code: 'fi' as const, name: 'Suomi' }];
  return {
    authenticated: raw.authenticated === true,
    locale: isLocale(raw.locale) && enabled.some((item) => item.code === raw.locale)
      ? raw.locale : enabled[0].code,
    locales: enabled,
    role: typeof raw.role === 'string' && raw.role ? raw.role.slice(0, 40) : 'guest',
    name: typeof raw.name === 'string' && raw.name ? raw.name.slice(0, 200) : null,
    picture: typeof raw.picture === 'string' && raw.picture ? raw.picture.slice(0, 2048) : null,
    globalAdmin: raw.global_admin === true,
    hasAdminAccess: raw.has_admin_access === true,
    unread: typeof raw.unread === 'number' && Number.isFinite(raw.unread) && raw.unread > 0
      ? Math.min(Math.floor(raw.unread), 999) : 0,
    fundraising: raw.fundraising === true,
    siteAnalyticsEnabled: raw.site_analytics_enabled === true,
    matomoEnabled: raw.matomo_enabled === true,
  };
}

type PublicSummary = { endpoint: string; value: SessionSummary; expiresAt: number };
let publicSummary: PublicSummary | null = null;
let publicPending: { endpoint: string; promise: Promise<SessionSummary> } | null = null;

function copySession(value: SessionSummary): SessionSummary {
  return { ...value, locales: value.locales.map((locale) => ({ ...locale })) };
}

async function requestSession(endpoint: string, cookie: string | undefined,
  timeoutMs: number): Promise<SessionSummary | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(endpoint, {
      signal: controller.signal,
      headers: { Accept: 'application/json', ...(cookie ? { Cookie: cookie } : {}) },
    });
    if (!response.ok) return null;
    const value: unknown = await response.json();
    if (!value || typeof value !== 'object' || typeof (value as Record<string, unknown>).authenticated !== 'boolean') return null;
    return normalizeSession(value);
  } catch {
    // A failure falls back after the bounded timeout and is never cached.
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/** Cookie-bearing requests stay private; only cookieless public configuration is shared. */
export async function fetchSession(endpoint: string, cookie: string | undefined,
  timeoutMs = 1200): Promise<SessionSummary> {
  if (cookie) return (await requestSession(endpoint, cookie, timeoutMs)) ?? copySession(anonymousSession);
  if (publicSummary?.endpoint === endpoint && publicSummary.expiresAt > Date.now()) {
    return copySession(publicSummary.value);
  }
  if (publicPending?.endpoint !== endpoint) {
    const promise = requestSession(endpoint, undefined, timeoutMs).then((value) => {
      if (value && !value.authenticated) {
        const publicValue = { ...value, role: 'guest', name: null, picture: null,
          globalAdmin: false, hasAdminAccess: false, unread: 0 };
        publicSummary = { endpoint, value: publicValue, expiresAt: Date.now() + 30_000 };
        return publicValue;
      }
      return copySession(anonymousSession);
    }).finally(() => {
      if (publicPending?.promise === promise) publicPending = null;
    });
    publicPending = { endpoint, promise };
  }
  return copySession(await publicPending.promise);
}

/** Browser refresh after the session changes outside the app. */
export async function refreshSession(endpoint: string): Promise<SessionSummary> {
  try {
    const response = await fetch(endpoint, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
    if (!response.ok) return { ...anonymousSession };
    return normalizeSession(await response.json());
  } catch {
    return { ...anonymousSession };
  }
}
