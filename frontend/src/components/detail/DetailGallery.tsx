import { useEffect, useRef, useState } from 'react';
import { safeHref } from './content';
import type { DetailMessages } from './types';

export function DetailGallery({ images, title, messages }: { images: string[]; title: string; messages: DetailMessages }) {
  const sources = [...new Set(images.map(safeHref).filter((value): value is string => Boolean(value)))];
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);
  const [failed, setFailed] = useState<string[]>([]);
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const usable = sources.filter(source => !failed.includes(source));
  const selected = Math.min(active, Math.max(0, usable.length - 1));
  useEffect(() => {
    if (open && usable.length) dialog.current?.showModal();
    else dialog.current?.close();
  }, [open, usable.length]);
  function close() { setOpen(false); trigger.current?.focus(); }
  function step(direction: number) { setActive((selected + direction + usable.length) % usable.length); }
  if (!sources.length) return null;
  if (!usable.length) return <p className="detail-note">{messages.imageUnavailable}</p>;
  return <section className="detail-gallery" aria-label={messages.gallery}>
    <button ref={trigger} className="detail-gallery__cover" type="button" onClick={() => setOpen(true)} aria-label={messages.openImage}>
      <img src={usable[selected]} alt={title} loading="eager" decoding="async" referrerPolicy="no-referrer"
        onError={() => setFailed(current => [...current, usable[selected]])} />
      <span>{messages.openImage}{usable.length > 1 ? ` · ${selected + 1}/${usable.length}` : ''}</span>
    </button>
    {usable.length > 1 && <div className="detail-gallery__controls">
      <button type="button" className="detail-button detail-button--quiet" onClick={() => step(-1)}>{messages.previous}</button>
      <span aria-live="polite">{selected + 1} / {usable.length}</span>
      <button type="button" className="detail-button detail-button--quiet" onClick={() => step(1)}>{messages.next}</button>
    </div>}
    <dialog ref={dialog} className="detail-lightbox" aria-label={`${messages.gallery}: ${title}`} onCancel={() => close()} onClose={() => { if (open) close(); }}
      onKeyDown={event => { if (event.key === 'ArrowLeft') { event.preventDefault(); step(-1); } if (event.key === 'ArrowRight') { event.preventDefault(); step(1); } }}>
      <div className="detail-lightbox__toolbar"><strong>{title}</strong><button type="button" className="detail-button" onClick={close}>{messages.close}</button></div>
      <img src={usable[selected]} alt={title} referrerPolicy="no-referrer" onError={() => setFailed(current => [...current, usable[selected]])} />
      {usable.length > 1 && <div className="detail-gallery__controls"><button type="button" className="detail-button" onClick={() => step(-1)}>{messages.previous}</button>
        <span>{selected + 1} / {usable.length}</span><button type="button" className="detail-button" onClick={() => step(1)}>{messages.next}</button></div>}
    </dialog>
  </section>;
}
