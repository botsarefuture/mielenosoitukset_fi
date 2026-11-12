/**
 * Portable configuration for the public React application.
 *
 * The application is hosted outside Flask's template rendering, so every URL it
 * links to is declared here from the existing public route paths. No session,
 * permission or database access is decided in this module.
 */

export type AppLocale = 'fi' | 'en' | 'sv';

export type AppUrls = {
  home: string; demonstrations: string; today: string; cities: string; submit: string; calendar: string;
  info: string; pride: string; privacy: string; contact: string; cityAdmin: string; guides: string; developer: string;
  login: string; register: string; logout: string; profile: string; settings: string; admin: string;
  notifications: { list: string; markRead: string; all: string };
  attendance: string; session: string; authMe: string; rss: string; fundraising: string;
  detail: string; series: string; tag: string;
  language: (code: AppLocale) => string;
};

export type AppConfig = {
  origin: string;
  apiBase: string;
  homeApi: string;
  locale: AppLocale;
  locales: { code: AppLocale; name: string; active: boolean; href: string }[];
  urls: AppUrls;
};

export const LOCALE_NAMES: Record<AppLocale, string> = { fi: 'Suomi', en: 'English', sv: 'Svenska' };

export function isLocale(value: unknown): value is AppLocale {
  return value === 'fi' || value === 'en' || value === 'sv';
}

/** Existing public route paths. Changing one here must change the route too. */
const ROUTES = {
  home: '/', demonstrations: '/demonstrations', today: '/mielenosoitukset-tanaan', cities: '/cities', submit: '/submit',
  calendar: '/calendar/', info: '/info', pride: '/pride-nakyvaksi', privacy: '/privacy',
  contact: '/contact', cityAdmin: '/kaupunkiadmin', guides: '/ohjeet', developer: '/developer', fundraising: '/keräys',
  login: '/users/auth/login', register: '/users/auth/register', logout: '/users/auth/logout',
  profile: '/users/profile/', settings: '/users/auth/settings', admin: '/admin/dashboard',
  notificationsList: '/api/notifications/', notificationsMarkRead: '/api/notifications/mark-read',
  notificationsAll: '/api/notifications/all', attendance: '/api/friends-attending',
  session: '/api/session', authMe: '/api/auth/me', rss: '/demonstrations.rss',
  detail: '/demonstration/__ID__', series: '/demonstration/__ID__/children', tag: '/tag/__TAG__',
} as const;

export function appConfig(options: {
  origin: string; apiBase: string; locale?: unknown; path?: string;
  /** Public locales enabled by the server configuration, never guessed here. */
  locales?: { code: string; name?: string }[];
}): AppConfig {
  const configured = (options.locales ?? [])
    .filter((item): item is { code: AppLocale; name?: string } => isLocale(item.code))
    .map((item) => ({ code: item.code, name: item.name || LOCALE_NAMES[item.code] }));
  const available = configured.length ? configured : [{ code: 'fi' as AppLocale, name: LOCALE_NAMES.fi }];
  const locale: AppLocale = isLocale(options.locale) && available.some((item) => item.code === options.locale)
    ? options.locale : available[0].code;
  // The server returns the requested public path for a language switch so the
  // visitor stays on the same page after the cookie changes.
  const next = options.path && options.path.startsWith('/') ? options.path : ROUTES.home;
  const apiBase = options.apiBase.replace(/\/+$/, '');
  return {
    origin: options.origin.replace(/\/+$/, ''),
    apiBase,
    homeApi: `${apiBase}/home`,
    locale,
    locales: available.map((item) => ({
      code: item.code, name: item.name, active: item.code === locale,
      href: `/set_language/${item.code}?next=${encodeURIComponent(next)}`,
    })),
    urls: {
      home: ROUTES.home, demonstrations: ROUTES.demonstrations, today: ROUTES.today, cities: ROUTES.cities,
      submit: ROUTES.submit, calendar: ROUTES.calendar, info: ROUTES.info, pride: ROUTES.pride,
      privacy: ROUTES.privacy, contact: ROUTES.contact, cityAdmin: ROUTES.cityAdmin, guides: ROUTES.guides,
      developer: ROUTES.developer, fundraising: ROUTES.fundraising,
      login: ROUTES.login, register: ROUTES.register, logout: ROUTES.logout,
      profile: ROUTES.profile, settings: ROUTES.settings, admin: ROUTES.admin,
      notifications: { list: ROUTES.notificationsList, markRead: ROUTES.notificationsMarkRead,
        all: ROUTES.notificationsAll },
      attendance: ROUTES.attendance, session: ROUTES.session, authMe: ROUTES.authMe, rss: ROUTES.rss,
      detail: ROUTES.detail, series: ROUTES.series, tag: ROUTES.tag,
      language: (code: AppLocale) => `/set_language/${code}`,
    },
  };
}
