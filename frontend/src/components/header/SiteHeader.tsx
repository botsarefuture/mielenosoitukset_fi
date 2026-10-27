import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import type { HeaderProps } from './types';
import { Icon, NavigationLink } from './NavigationLink';
import { LanguageSwitcher } from './LanguageSwitcher';
import { ThemeToggle } from './ThemeToggle';
import { UserMenu } from './UserMenu';
import { NotificationMenu } from './NotificationMenu';

export function SiteHeader(props: HeaderProps) {
  const { messages: text, account } = props;
  const [mobile, setMobile] = useState(() => matchMedia('(max-width: 768px)').matches);
  const [open, setOpen] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const pendingFocus = useRef<HTMLElement | null>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const openRef = useRef(false);
  openRef.current = open;
  function closeDrawer(restoreFocus = true) {
    if (restoreFocus) pendingFocus.current = returnFocus.current;
    returnFocus.current = null;
    setOpen(false);
  }
  useEffect(() => {
    try { localStorage.setItem('user_role', props.role); } catch { /* Storage is optional. */ }
    const query = matchMedia('(max-width: 768px)');
    function resize() {
      if (!query.matches && openRef.current) {
        list.current?.querySelector<HTMLElement>('.nav-link[aria-current="page"], .nav-link')?.focus();
      }
      setMobile(query.matches); setOpen(false); returnFocus.current = null;
    }
    query.addEventListener('change', resize);
    return () => query.removeEventListener('change', resize);
  }, [props.role]);
  useLayoutEffect(() => {
    document.body.classList.toggle('public-nav-open', mobile && open);
    if (mobile && open) close.current?.focus();
    else if (pendingFocus.current) { pendingFocus.current.focus(); pendingFocus.current = null; }
    return () => document.body.classList.remove('public-nav-open');
  }, [mobile, open]);
  function keydown(event: KeyboardEvent) {
    if (!mobile || !open) return;
    if (event.key === 'Escape') { event.preventDefault(); closeDrawer(); return; }
    if (event.key !== 'Tab') return;
    const focusable = Array.from(list.current?.querySelectorAll<HTMLElement>('a, button') ?? [])
      .filter(element => !element.hasAttribute('disabled') && element.getClientRects().length > 0);
    const first = focusable[0], last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  }
  return <div className="public-header-ready" onKeyDown={keydown}>
    <a href="#main-content" className="skip-link">{text.skip}</a>
    <header className={`top-header public-site-header${props.fundraising ? ' public-site-header--fundraising' : ''}`} role="banner">
      <div className="container"><div className="branding">
        <a href={props.home} className="logo" aria-label={text.home}>{props.brand}</a>
      </div>
      {props.fundraising && <a className="fundraising-header-link" href={props.fundraising} lang="fi">
        <i className="fas fa-heart" aria-hidden="true" /> Tutustu pienkeräykseen
      </a>}
      <LanguageSwitcher languages={props.languages} messages={text} />
      </div>
    </header>
    <nav className="main-nav public-main-nav" role="navigation" aria-label={text.navigation}>
      <div className="nav-container">
        <button className="mobile-menu-toggle" id="mobile-menu-toggle" type="button" ref={toggle}
          aria-expanded={mobile && open} aria-controls="main-nav-list" aria-label={open ? text.closeMenu : text.openMenu}
          onClick={() => { returnFocus.current = toggle.current; setOpen(true); }}>
          <Icon name="fa-bars" /><Icon name="fa-times" />
        </button>
        <ul className={`nav-list${mobile && open ? ' active' : ''}`} id="main-nav-list" ref={list}
          aria-hidden={mobile ? !open : undefined} inert={mobile && !open ? true : undefined}
          onClick={event => { if ((event.target as Element).closest('a')) closeDrawer(false); }}>
          <li className="mobile-nav-header"><span className="logo mobile-nav-title">{text.menu}</span>
            <button className="mobile-close" id="mobile-menu-close" type="button" ref={close}
              aria-label={text.close} onClick={() => closeDrawer()}><Icon name="fa-times" /></button>
          </li>
          {props.links.map(link => <li key={link.href}><NavigationLink link={link} current={props.path === link.href} /></li>)}
          {account && <><NotificationMenu notifications={props.notifications} messages={text} path={props.path} />
            <UserMenu account={account} label={text.userMenu} /></>}
          {account?.globalAdmin && <li className="mobile-only"><div className="admin-alert" role="alert">
            <Icon name="fa-exclamation-triangle" /><span>{text.adminWarning}</span>
          </div></li>}
          <ThemeToggle messages={text} />
        </ul>
      </div>
    </nav>
  </div>;
}
