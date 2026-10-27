import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import type { HeaderProps } from './types';
import { Icon } from './NavigationLink';

export function UserMenu({ account, label }: { account: NonNullable<HeaderProps['account']>; label: string }) {
  const [open, setOpen] = useState(false);
  const manualOpen = useRef(false);
  const wrap = useRef<HTMLLIElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  useEffect(() => {
    function outside(event: Event) {
      if (!wrap.current?.contains(event.target as Node)) { setOpen(false); manualOpen.current = false; }
    }
    document.addEventListener('pointerdown', outside);
    document.addEventListener('focusin', outside);
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('focusin', outside);
    };
  }, []);
  function keydown(event: KeyboardEvent) {
    const items = Array.from(menu.current?.querySelectorAll('a') ?? []);
    const index = items.indexOf(document.activeElement as HTMLAnchorElement);
    let next: number | undefined;
    if (event.key === 'Escape') {
      event.preventDefault(); event.stopPropagation(); setOpen(false); manualOpen.current = false; button.current?.focus(); return;
    }
    if (event.key === 'ArrowDown') next = (index + 1) % items.length;
    if (event.key === 'ArrowUp') next = (index - 1 + items.length) % items.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = items.length - 1;
    if (next !== undefined) {
      event.preventDefault(); setOpen(true); manualOpen.current = true;
      requestAnimationFrame(() => items[next!]?.focus());
    }
  }
  return <li className="user-dropdown" id="user-dropdown" ref={wrap} aria-expanded={open}
    onKeyDown={keydown}
    onPointerEnter={() => { if (matchMedia('(min-width: 769px) and (hover: hover)').matches) setOpen(true); }}
    onPointerLeave={() => { if (!manualOpen.current) setOpen(false); }}>
    <button className="user-toggle" id="user-toggle-btn" type="button" ref={button}
      aria-haspopup="menu" aria-expanded={open} aria-controls="user-dropdown-menu"
      aria-label={label} onClick={() => { const next = !manualOpen.current; manualOpen.current = next; setOpen(next); }}>
      {account.picture && <img src={account.picture} alt="" className="profile-picture" aria-hidden="true" />}
      <span>{account.name}</span><Icon name="fa-chevron-down" />
    </button>
    <div className="dropdown-menu" id="user-dropdown-menu" role="menu" aria-labelledby="user-toggle-btn" ref={menu}>
      <ul>{account.links.map(link => <li key={link.href} role="none">
        <a href={link.href} role="menuitem"><Icon name={link.icon} /><span>{link.label}</span></a>
      </li>)}</ul>
    </div>
  </li>;
}
