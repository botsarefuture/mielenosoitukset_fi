import { useEffect, useRef, useState } from 'react';
import { PublicListingPage } from './PublicListingPage';
import { organizationCopy as text } from '../components/organization/copy';
import type { OrganizationPageProps, OrganizationPermissions, OrganizationUrls } from '../components/organization/types';
import '../components/organization/organization.css';
import '../../../mielenosoitukset_fi/static/css/toolbox.css';

function Icon({ name, brand = false }: { name: string; brand?: boolean }) {
  return <i className={`${brand ? 'fa-brands' : 'fa-solid'} fa-${name}`} aria-hidden="true" />;
}

/** Public profile links are data, never executable URLs or HTML. */
function publicLink(value: string | null | undefined): string | null {
  if (!value || /[\u0000-\u001f\u007f]/.test(value)) return null;
  const trimmed = value.trim();
  if (trimmed.startsWith('/') && !trimmed.startsWith('//') && !trimmed.includes('\\')) return trimmed;
  try {
    const url = new URL(trimmed);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

function Tool({ permissions, urls, name }: { permissions: OrganizationPermissions; urls: OrganizationUrls; name: string }) {
  const [collapsed, collapse] = useState(() => {
    if (window.matchMedia('(max-width: 35rem)').matches) return true;
    try { return window.sessionStorage.getItem('publicToolboxCollapsed') !== 'false'; }
    catch { return true; }
  });
  useEffect(() => {
    if (window.matchMedia('(max-width: 35rem)').matches) return;
    try { window.sessionStorage.setItem('publicToolboxCollapsed', String(collapsed)); }
    catch { /* Storage is optional in private browsing. */ }
  }, [collapsed]);
  const visible = Object.values(permissions).some(Boolean);
  if (!visible) return null;
  return <aside id="toolbox-sidebar" className={`public-toolbox${collapsed ? ' collapsed' : ''}`} aria-label={text.toolbox}>
    <div className="public-toolbox__card">
      <div className="public-toolbox__header">
        <div className="public-toolbox__identity">
          <span className="public-toolbox__identity-icon"><Icon name="sliders" /></span>
          <div className="public-toolbox__identity-copy"><span className="public-toolbox__eyebrow">{text.toolbox}</span>
            <h2 className="public-toolbox__title" title={name}>{name}</h2></div>
        </div>
        <button className="btn btn-sm collapse-toggle" type="button" aria-expanded={!collapsed}
          aria-controls="organization-toolbox-actions" aria-label={collapsed ? text.expand : text.collapse}
          onClick={() => collapse(value => !value)}><Icon name={collapsed ? 'toolbox' : 'xmark'} />
          <span className="collapse-toggle__label">{text.toolbox}</span>
        </button>
      </div>
      <div className="public-toolbox__body" id="organization-toolbox-actions" hidden={collapsed}>
        <nav className="public-toolbox__actions" aria-label={text.actions}>
          {(permissions.VIEW_ORGANIZATION || permissions.INVITE_TO_ORGANIZATION) && <a href={urls.adminView}
            className="public-toolbox__action public-toolbox__action--primary"><span className="public-toolbox__action-icon"><Icon name="sliders" /></span>
            <span className="public-toolbox__action-label">{text.admin}</span><Icon name="chevron-right" /></a>}
          {permissions.EDIT_ORGANIZATION && <a href={urls.adminEdit} className="public-toolbox__action">
            <span className="public-toolbox__action-icon"><Icon name="pen-to-square" /></span><span className="public-toolbox__action-label">{text.edit}</span><Icon name="chevron-right" /></a>}
          {permissions.DELETE_ORGANIZATION && <div className="public-toolbox__danger-zone"><a href={urls.adminDelete}
            className="public-toolbox__action public-toolbox__action--danger"><span className="public-toolbox__action-icon"><Icon name="trash-can" /></span>
            <span className="public-toolbox__action-label">{text.remove}</span><Icon name="chevron-right" /></a></div>}
        </nav>
      </div>
    </div>
  </aside>;
}

function BackToTop() {
  const host = useRef<HTMLElement | Window>(window);
  const marker = useRef<HTMLButtonElement>(null);
  const [visible, show] = useState(false);
  useEffect(() => {
    for (let node = marker.current?.parentElement; node; node = node.parentElement) {
      if (node !== document.scrollingElement && /auto|scroll/.test(getComputedStyle(node).overflowY)) { host.current = node; break; }
    }
    const update = () => show((host.current instanceof Window ? window.scrollY : host.current.scrollTop) > 300);
    const scroller = host.current;
    scroller.addEventListener('scroll', update, { passive: true }); update();
    return () => scroller.removeEventListener('scroll', update);
  }, []);
  return <button ref={marker} type="button" className={`back-to-top${visible ? ' visible' : ''}`} id="backToTop"
    aria-label={text.top} onClick={() => host.current.scrollTo({ top: 0,
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' })}><Icon name="arrow-up" /></button>;
}

/** Complete public profile. Public card data and private actions have separate contracts. */
export function OrganizationPage({ organization: org, authenticated, privateState, urls, listing }: OrganizationPageProps) {
  const [following, follow] = useState(privateState?.following ?? false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);
  const active = useRef<AbortController | null>(null);
  const busy = useRef(false);
  useEffect(() => { follow(privateState?.following ?? false); }, [org._id, privateState?.following]);
  useEffect(() => () => { active.current?.abort(); active.current = null; }, []);
  async function changeFollow() {
    if (busy.current || !privateState) return;
    busy.current = true; setPending(true); setError(false);
    const controller = new AbortController(); active.current = controller;
    const timer = window.setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(following ? urls.unfollow : urls.follow, {
        method: 'POST', credentials: 'same-origin', signal: controller.signal,
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      });
      if (!response.ok || response.redirected || !response.headers.get('content-type')?.includes('application/json')) throw new Error('Follow failed');
      const value = await response.json();
      if (value.status !== 'OK' || typeof value.following !== 'boolean') throw new Error('Invalid follow response');
      follow(value.following);
    } catch { if (active.current === controller) setError(true); }
    finally {
      clearTimeout(timer);
      if (active.current === controller) { busy.current = false; setPending(false); active.current = null; }
    }
  }
  const logo = publicLink(org.logo);
  const website = publicLink(org.website);
  const socials = Object.entries(org.social_media_links).flatMap(([platform, value]) => {
    const href = publicLink(value);
    return href ? [{ platform, href }] : [];
  });
  const email = org.email && !/[\u0000-\u001f\u007f]/.test(org.email) ? org.email : null;
  const incomplete = !org.verified && (!website || !email || !socials.length);
  const platforms: Record<string, string> = { facebook: 'Facebook', twitter: 'Twitter', instagram: 'Instagram', linkedin: 'LinkedIn', youtube: 'YouTube', tiktok: 'TikTok' };
  return <article className="organization-page">
    <section className="org-hero site-hero">
      <div className="org-hero-content"><div className="org-hero-header">
        <div className="org-logo-wrapper">{logo
          ? <img src={logo} alt={`${text.logo} ${org.name}`} decoding="async" referrerPolicy="no-referrer" />
          : <div className="org-logo-placeholder"><Icon name="building" /></div>}</div>
        <div className="org-hero-info">
          <h1 className="org-name">{org.name}</h1>
          {org.description && <p className="org-desc">{org.description}</p>}
        </div>
      </div>
      {org.verified && <div className="verified-banner" tabIndex={0} aria-describedby="organization-verification-help">
        <Icon name="shield-halved" /><span>{text.verifiedNote}</span>
        <span className="tooltip-text" id="organization-verification-help" role="tooltip">{text.verifiedHelp}</span>
      </div>}</div>
    </section>
    <section className="follow-card">
      <div className="follow-card-text"><h2>{text.stayUpdated}</h2><p>{text.followIntro}</p></div>
      <div className="follow-card-action">{authenticated ? <>
        <button type="button" className={`follow-pill-button${following ? ' is-following' : ''}`} id="org-follow-btn"
          aria-pressed={following} aria-busy={pending} disabled={pending || !privateState} onClick={() => void changeFollow()}>
          <span className={`follow-icon ${following ? 'fa-solid' : 'fa-regular'} fa-star`} aria-hidden="true" />
          <span className="follow-label" aria-live="polite">{!privateState ? text.loading : following ? text.following.toLocaleUpperCase('fi') : text.follow.toLocaleUpperCase('fi')}</span>
        </button>
        {error && <p className="org-action-error" role="alert">{text.followError}</p>}
      </> : <p className="org-follow-login">{text.loginPrompt} <a href={urls.login}>{text.login}</a></p>}</div>
    </section>
    {authenticated && privateState?.invited && <section className="invite-banner" aria-labelledby="organization-invite-title">
      <div className="invite-content"><Icon name="envelope-open-text" /><div>
        <h2 id="organization-invite-title">{text.invited} {org.name}!</h2><p>{text.inviteHelp}</p>
      </div></div>
      <div className="invite-actions"><form method="POST" action={urls.acceptInvite}>
        <button type="submit" className="org-action org-action--success"><Icon name="check" />{text.accept}</button>
      </form><form method="POST" action={urls.declineInvite}>
        <button type="submit" className="org-action"><Icon name="xmark" />{text.decline}</button>
      </form></div>
    </section>}
    <section className="section-card org-contact-card" aria-labelledby="organization-contact-title">
      <h2 className="section-title" id="organization-contact-title"><Icon name="address-card" />{text.contacts}</h2>
      <div className="contact-methods">
        {email && <a href={`mailto:${encodeURIComponent(email)}`} className="contact-item"><span className="contact-icon"><Icon name="envelope" /></span>
          <div className="contact-info"><h3>{text.email}</h3><p>{email}</p></div></a>}
        {website && <a href={website} target="_blank" rel="noopener noreferrer" className="contact-item"><span className="contact-icon"><Icon name="globe" /></span>
          <div className="contact-info"><h3>{text.website}</h3><p>{org.website}</p></div></a>}
      </div>
      {socials.length > 0 && <><h3 className="section-title"><Icon name="share-nodes" />{text.social}</h3><div className="socials">
        {socials.map(({ platform, href }) => {
          const username = new URL(href, window.location.origin).pathname.split('/').filter(Boolean).at(-1) ?? '';
          const knownPlatform = Object.hasOwn(platforms, platform);
          return <a key={platform} href={href} target="_blank" rel="noopener noreferrer" className="social-item">
            <span className="social-icon"><Icon name={knownPlatform ? platform : 'share-nodes'} brand={knownPlatform} /></span>
            <div className="social-info"><div className="platform">{knownPlatform ? platforms[platform] : platform}</div>
              <div className="username">{username && !username.startsWith('@') ? `@${username}` : username}</div></div>
          </a>;
        })}
      </div></>}
    </section>
    {incomplete && <section className="help-us-banner"><div className="help-us-content"><span className="help-us-icon"><Icon name="circle-info" /></span>
      <div className="help-us-text"><h2>{text.missing}</h2><p>{text.missingHelp}</p></div></div>
      <a href={urls.fill} className="help-us-button"><Icon name="pen-to-square" />{text.fill}</a>
    </section>}
    <section id="demos"><PublicListingPage {...listing} /></section>
    {authenticated && privateState && <Tool permissions={privateState.permissions} urls={urls} name={org.name} />}
    <BackToTop />
  </article>;
}
