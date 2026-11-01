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
};

export const anonymousSession: SessionSummary = {
  authenticated: false, locale: 'fi', locales: [{ code: 'fi', name: 'Suomi' }],
  role: 'guest', name: null, picture: null,
  globalAdmin: false, hasAdminAccess: false, unread: 0, fundraising: false,
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
  };
}

/** Server-side read of the Flask summary for the incoming session cookie. */
export async function fetchSession(endpoint: string, cookie: string | undefined,
  timeoutMs = 1200): Promise<SessionSummary> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(endpoint, {
      signal: controller.signal,
      headers: { Accept: 'application/json', ...(cookie ? { Cookie: cookie } : {}) },
    });
    if (!response.ok) return { ...anonymousSession };
    return normalizeSession(await response.json());
  } catch {
    // A slow or unavailable Flask must not block the public page.
    return { ...anonymousSession };
  } finally {
    clearTimeout(timer);
  }
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
