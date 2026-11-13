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
  /** The contact page's one-time form token, feedback and field limits; anonymous visitors get one too. */
  contactForm?: {
    enabled: boolean; csrfToken?: string; messages: { category: string; message: string }[];
    limits: { nameMax: number; emailMax: number; messageMin: number; messageMax: number };
  };
  /** True when the server's read-only auth bridge is on; the client may then use `urls.authMe`. */
  authBridge?: boolean;
  /** The visitor sent a cookie but the server could not read the session (timeout, error). Not the same as signed out. */
  unverified?: boolean;
  /** Signed token the sign-out form must post; only present for a signed-in visitor. */
  logoutToken?: string;
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
  // An anonymous visitor only ever gets the pending-message flag: no membership, invitation or permission.
  const member = raw.authenticated === true;
  const organization = scoped && typeof scoped.id === 'string' && /^[a-f\d]{24}$/.test(scoped.id)
    ? { id: scoped.id, following: member && scoped.following === true, invited: member && scoped.invited === true,
      hasMessages: scoped.has_messages === true,
      permissions: { VIEW_ORGANIZATION: member && permissions.VIEW_ORGANIZATION === true,
        EDIT_ORGANIZATION: member && permissions.EDIT_ORGANIZATION === true,
        DELETE_ORGANIZATION: member && permissions.DELETE_ORGANIZATION === true,
        INVITE_TO_ORGANIZATION: member && permissions.INVITE_TO_ORGANIZATION === true } } : undefined;
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
    ...(raw.auth_bridge === true ? { authBridge: true } : {}),
    ...(raw.authenticated === true && typeof raw.logout_token === 'string' && /^[\w.-]{20,400}$/.test(raw.logout_token)
      ? { logoutToken: raw.logout_token } : {}),
    ...(organization ? { organization } : {}),
    ...(raw.authenticated === true && raw.translation_join && typeof raw.translation_join === 'object'
      ? { translationJoin: normalizeTranslationJoin(raw.translation_join as Record<string, unknown>) } : {}),
    ...(raw.contact_form && typeof raw.contact_form === 'object' && !Array.isArray(raw.contact_form)
      ? { contactForm: normalizeContactForm(raw.contact_form as Record<string, unknown>) } : {}),
  };
}

function formToken(value: unknown): string | undefined {
  return typeof value === 'string' && /^[A-Za-z0-9_-]{43}$/.test(value) ? value : undefined;
}

function flashMessages(value: unknown): { category: string; message: string }[] {
  return Array.isArray(value) ? value.slice(0, 10).flatMap(entry => {
    if (!Array.isArray(entry) || typeof entry[1] !== 'string') return [];
    const category = ['success', 'error', 'danger', 'warning', 'info'].includes(entry[0]) ? String(entry[0]) : 'default';
    return [{ category, message: entry[1].slice(0, 1000) }];
  }) : [];
}

function normalizeContactForm(raw: Record<string, unknown>): NonNullable<SessionSummary['contactForm']> {
  const limits = raw.limits && typeof raw.limits === 'object' ? raw.limits as Record<string, unknown> : {};
  const bounded = (value: unknown, fallback: number, max: number) =>
    typeof value === 'number' && Number.isInteger(value) && value > 0 && value <= max ? value : fallback;
  return {
    enabled: raw.enabled === true,
    csrfToken: formToken(raw.csrf_token),
    messages: flashMessages(raw.messages),
    limits: { nameMax: bounded(limits.name_max, 120, 1000), emailMax: bounded(limits.email_max, 254, 1000),
      messageMin: bounded(limits.message_min, 10, 1000), messageMax: bounded(limits.message_max, 5000, 100000) },
  };
}

function normalizeTranslationJoin(raw: Record<string, unknown>): NonNullable<SessionSummary['translationJoin']> {
  return { joined: raw.joined === true, csrfToken: formToken(raw.csrf_token), messages: flashMessages(raw.messages) };
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
