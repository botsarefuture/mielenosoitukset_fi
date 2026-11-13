import type { AppConfig } from './config';
import type { Catalog } from './i18n';
import type { SessionSummary } from './session';

const SOCIAL = [
  { href: 'https://www.instagram.com/mielenosoitukset', icon: 'fa-instagram', label: 'Instagram' },
  { href: 'https://www.facebook.com/mielenosoitukset', icon: 'fa-facebook', label: 'Facebook' },
  { href: 'https://www.tiktok.com/@mielenosoitukset', icon: 'fa-tiktok', label: 'TikTok' },
  { href: 'https://mastodon.social/@mielenosoitukset', icon: 'fa-mastodon', label: 'Mastodon' },
] as const;

/** The existing public footer, owned by React in the standalone application. */
export function SiteFooter({ config, session, text }: {
  config: AppConfig; session: SessionSummary; text: Catalog;
}) {
  const links = [
    { href: config.urls.info, label: text.footer.info },
    { href: config.urls.privacy, label: text.footer.privacy },
    { href: config.urls.contact, label: text.footer.contact },
    { href: config.urls.guides, label: text.footer.guides },
    { href: config.urls.developer, label: text.footer.developer },
  ];
  return <footer className="footer public-site-footer">
    <div className="container-header-footer public-site-footer__inner">
      <p className="public-site-footer__brand">&copy; 2026 Mielenosoitukset.fi · {text.footer.rights}</p>
      <nav aria-label={text.footer.navigation}>
        <ul className="footer-links public-site-footer__links">
          {links.map((link) => <li key={link.href}><a href={link.href}>{link.label}</a></li>)}
        </ul>
      </nav>
      <ul className="social-media-links public-site-footer__social" aria-label={text.footer.social}>
        {SOCIAL.map((item) => <li key={item.href}>
          <a href={item.href} target="_blank" rel="noopener noreferrer">
            <i className={`fab ${item.icon}`} aria-hidden="true" /> {item.label}
          </a>
        </li>)}
      </ul>
      <ul className="footer-links auth-buttons public-site-footer__auth" aria-label={text.footer.account}>
        {session.authenticated
          ? <li>{session.logoutToken
            ? <form method="post" action={config.urls.logout} className="footer-logout-form">
              <input type="hidden" name="logout_token" value={session.logoutToken} />
              <button type="submit" className="footer-logout-button">{text.account.logout}</button>
            </form>
            // Without a token the link opens the confirmation page; a GET never signs anyone out.
            : <a href={config.urls.logout}>{text.account.logout}</a>}</li>
          : <><li><a href={config.urls.login}>{text.account.login}</a></li>
            <li><a href={config.urls.register}>{text.account.register}</a></li></>}
      </ul>
    </div>
  </footer>;
}
