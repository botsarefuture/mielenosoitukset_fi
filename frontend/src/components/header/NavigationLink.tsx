import type { HeaderLink } from './types';

export function Icon({ name }: { name: string }) {
  return <i className={`fa-solid ${name}`} aria-hidden="true" />;
}

export function NavigationLink({ link, current }: { link: HeaderLink; current: boolean }) {
  return <a href={link.href} className={`nav-link${current ? ' active' : ''}`}
    aria-label={link.label} aria-current={current ? 'page' : undefined}>
    <Icon name={link.icon} /><span>{link.label}</span>
  </a>;
}
