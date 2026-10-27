import { useEffect, useState } from 'react';
import type { HeaderMessages } from './types';

export function ThemeToggle({ messages }: { messages: HeaderMessages }) {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'));
  useEffect(() => {
    // Other existing page controls can still change the shared theme.
    const observer = new MutationObserver(() => setDark(document.documentElement.classList.contains('dark')));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);
  function toggle() {
    const next = !document.documentElement.classList.contains('dark');
    document.documentElement.classList.toggle('dark', next);
    document.documentElement.classList.toggle('light', !next);
    try { localStorage.setItem('theme', next ? 'dark' : 'light'); } catch { /* Theme still works without storage. */ }
    setDark(next);
  }
  return <li className="theme-toggle-item"><button type="button"
    className="theme-toggle theme-toggle-mobile" onClick={toggle}
    aria-label={dark ? messages.lightTheme : messages.darkTheme} aria-pressed={dark}>
    <i className={`fa-solid ${dark ? 'fa-sun' : 'fa-moon'} header-theme-icon`} aria-hidden="true" />
  </button></li>;
}
