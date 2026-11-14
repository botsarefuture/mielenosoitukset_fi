import { useEffect, useState } from 'react';
import { carrierLinkCopy as c, confirmCarrier, readCarrierLink, removeCarrier } from './pride-volunteer';
import type { CarrierLinkMode } from './pride-volunteer';

/** The page behind the links in the carrier mails: confirm the signup, or delete the data. One button, no action on load. */
export function PrideCarrierLink() {
  const [link, setLink] = useState<{ mode: CarrierLinkMode; token: string } | null>(null);
  const [state, setState] = useState<'idle' | 'working' | 'done'>('idle');
  const [error, setError] = useState('');
  useEffect(() => {
    const found = readCarrierLink(window.location.search, window.location.hash);
    setLink(found);
    if (found) document.getElementById('kantaja-linkki')?.scrollIntoView({ block: 'start' });
  }, []);
  if (!link) return null;
  const confirming = link.mode === 'vahvista';
  const act = async () => {
    setState('working');
    setError('');
    const result = await (confirming ? confirmCarrier : removeCarrier)(link.token);
    if (result.ok) { setState('done'); return; }
    setState('idle');
    setError(result.status === 410 ? c.expired : c.error);
  };
  return <section className="pride-volunteer-link pride-form" id="kantaja-linkki" aria-labelledby="pvl-title">
    <h2 id="pvl-title">{confirming ? c.confirmTitle : c.removeTitle}</h2>
    {state === 'done'
      ? <p role="status">{confirming ? c.confirmed : c.removed}</p>
      : <>
        <p>{confirming ? c.confirmIntro : c.removeIntro}</p>
        <button type="button" className="button" onClick={act} disabled={state === 'working' || !link.token}>
          {confirming ? c.confirmButton : c.removeButton}
        </button>
        <p className="pride-error" role="status">{error || (link.token ? '' : c.badLink)}</p>
      </>}
  </section>;
}
