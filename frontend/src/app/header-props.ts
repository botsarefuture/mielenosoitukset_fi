import type { HeaderProps } from '../components/header/types';
import type { AppConfig } from './config';
import type { Catalog } from './i18n';
import type { SessionSummary } from './session';

/**
 * Compose the existing shared header component without Flask template context.
 * The server still owns every permission: this only chooses which already
 * authorized links to display.
 */
export function headerProps(config: AppConfig, session: SessionSummary, text: Catalog, path: string): HeaderProps {
  const links = [
    { href: config.urls.home, label: text.nav.home, icon: 'fa-home' },
    { href: config.urls.demonstrations, label: text.nav.demonstrations, icon: 'fa-bullhorn' },
    { href: config.urls.cities, label: text.nav.cities, icon: 'fa-location-dot' },
    { href: config.urls.submit, label: text.nav.submit, icon: 'fa-plus-circle' },
  ];
  const account = session.authenticated && session.name ? {
    name: session.name,
    picture: session.picture,
    links: [
      { href: config.urls.profile, label: text.account.profile, icon: 'fa-user' },
      { href: config.urls.settings, label: text.account.settings, icon: 'fa-cog' },
      ...(session.hasAdminAccess
        ? [{ href: config.urls.admin, label: text.account.admin, icon: 'fa-gauge' }]
        : []),
      { href: config.urls.logout, label: text.account.logout, icon: 'fa-sign-out-alt',
        ...(session.logoutToken ? { post: session.logoutToken } : {}) },
    ],
    globalAdmin: session.globalAdmin,
  } : null;
  return {
    brand: 'Mielenosoitukset.fi',
    home: config.urls.home,
    path: path === '/mielenosoitukset-tanaan' || path.startsWith('/demonstration/') || path.startsWith('/tag/') || path.startsWith('/calendar') ? config.urls.demonstrations
      : path.startsWith('/city/') ? config.urls.cities : path,
    role: session.authenticated ? session.role : 'guest',
    links: account ? links : [...links, {
      href: config.urls.login, label: text.account.login, icon: 'fa-sign-in-alt',
    }],
    languages: config.locales,
    // The bar replaces the header link: with the bar flag on, the link never shows.
    fundraising: session.fundraising && !session.fundraisingBar.enabled ? config.urls.fundraising : null,
    account,
    notifications: {
      list: config.urls.notifications.list, markRead: config.urls.notifications.markRead,
      all: config.urls.notifications.all, unread: session.unread,
    },
    messages: text.header,
  };
}
