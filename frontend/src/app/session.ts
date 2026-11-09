import type { AppLocale } from './config';
import { isLocale } from './config';

/**
 * Header state for the public app.
 *
 * Flask owns the session and permissions. This summary is the only account data
 * the React host receives. The authenticated translation scope also provides
 * its existing CSRF form nonce and flash messages.
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
  submission?: { locales: AppLocale[]; defaultLanguage: AppLocale; canEditDemo: boolean };
  translationJoin?: { joined: boolean; csrfToken?: string; messages: { category: string; message: string }[] };
  organization?: {
    id: string; following: boolean; invited: boolean; hasMessages: boolean;
    permissions: Record<'VIEW_ORGANIZATION' | 'EDIT_ORGANIZATION' | 'DELETE_ORGANIZATION' | 'INVITE_TO_ORGANIZATION', boolean>;
  };
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
  const submission = raw.submission && typeof raw.submission === 'object'
    ? raw.submission as Record<string, unknown> : {};
  const submissionLocales = Array.isArray(submission.locales) ? submission.locales.filter(isLocale) : ['fi' as const];
  const locales = Array.isArray(raw.locales)
    ? raw.locales.flatMap((item) => {
      const entry = item as { code?: unknown; name?: unknown } | null;
      if (!entry || !isLocale(entry.code)) return [];
      const name = typeof entry.name === 'string' && entry.name ? entry.name.slice(0, 60) : entry.code;
      return [{ code: entry.code, name }];
    })
    : [];
  const enabled = locales.length ? locales : [{ code: 'fi' as const, name: 'Suomi' }];
  const scoped = raw.organization && typeof raw.organization === 'object'
    ? raw.organization as Record<string, unknown> : null;
  const permissions = scoped?.permissions && typeof scoped.permissions === 'object'
    ? scoped.permissions as Record<string, unknown> : {};
  const organization = raw.authenticated === true && scoped && typeof scoped.id === 'string' && /^[a-f\d]{24}$/.test(scoped.id)
    ? { id: scoped.id, following: scoped.following === true, invited: scoped.invited === true,
      hasMessages: scoped.has_messages === true,
      permissions: { VIEW_ORGANIZATION: permissions.VIEW_ORGANIZATION === true,
        EDIT_ORGANIZATION: permissions.EDIT_ORGANIZATION === true,
        DELETE_ORGANIZATION: permissions.DELETE_ORGANIZATION === true,
        INVITE_TO_ORGANIZATION: permissions.INVITE_TO_ORGANIZATION === true } } : undefined;
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
    submission: {
      locales: submissionLocales.length ? submissionLocales : ['fi'],
      defaultLanguage: isLocale(submission.default_language) && submissionLocales.includes(submission.default_language)
        ? submission.default_language : 'fi',
      canEditDemo: raw.authenticated === true && submission.can_edit_demo === true,
    },
    ...(organization ? { organization } : {}),
    ...(raw.authenticated === true && raw.translation_join && typeof raw.translation_join === 'object'
      ? { translationJoin: normalizeTranslationJoin(raw.translation_join as Record<string, unknown>) } : {}),
  };
}

function normalizeTranslationJoin(raw: Record<string, unknown>): NonNullable<SessionSummary['translationJoin']> {
  const csrfToken = typeof raw.csrf_token === 'string' && /^[A-Za-z0-9_-]{43}$/.test(raw.csrf_token)
    ? raw.csrf_token : undefined;
  const messages = Array.isArray(raw.messages) ? raw.messages.slice(0, 10).flatMap(entry => {
    if (!Array.isArray(entry) || typeof entry[1] !== 'string') return [];
    const category = ['success', 'error', 'danger', 'warning', 'info'].includes(entry[0]) ? String(entry[0]) : 'default';
    return [{ category, message: entry[1].slice(0, 1000) }];
  }) : [];
  return { joined: raw.joined === true, csrfToken, messages };
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
