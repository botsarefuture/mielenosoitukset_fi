import { useEffect, useRef, useState, type ComponentType } from 'react';
import './chat.css';

export function OrganizationChat({ authenticated }: { authenticated: boolean }) {
  const [open, setOpen] = useState(false);
  const [Panel, setPanel] = useState<ComponentType<{ onClose: () => void }> | null>(null);
  const [failed, setFailed] = useState(false);
  const launcher = useRef<HTMLButtonElement>(null);
  const load = () => { setFailed(false); void import('./ChatPanel').then(module => setPanel(() => module.default)).catch(() => setFailed(true)); };
  useEffect(() => {
    if (!open) return;
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') { setOpen(false); requestAnimationFrame(() => launcher.current?.focus()); } };
    document.addEventListener('keydown', escape);
    return () => document.removeEventListener('keydown', escape);
  }, [open]);
  if (!authenticated) return null;
  const close = () => { setOpen(false); requestAnimationFrame(() => launcher.current?.focus()); };
  return <div className="organization-chat">
    <button ref={launcher} id="chat-open-btn" type="button" hidden={open} aria-label="Avaa viestit" aria-expanded={open} aria-controls="chat-widget" onClick={() => { setOpen(true); if (!Panel) load(); }}>💬</button>
    {open && (Panel ? <Panel onClose={close} /> : <section id="chat-widget" role="dialog" aria-label="Viestit"><header>Viestit <button type="button" autoFocus onClick={close} aria-label="Sulje viestit">✕</button></header>{failed ? <p role="alert">Viestien lataaminen epäonnistui. <button type="button" onClick={load}>Yritä uudelleen</button></p> : <p role="status">Ladataan viestejä…</p>}</section>)}
  </div>;
}
