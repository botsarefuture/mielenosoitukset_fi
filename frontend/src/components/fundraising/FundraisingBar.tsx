import { useEffect, useState } from 'react';
import { barMilestone, barPhase, BAR_STORAGE_KEY, DONATION_ANCHOR, isDismissed, shortDate } from '../../app/fundraising-bar';
import type { FundraisingBarConfig, FundraisingBarText } from '../../app/fundraising-bar';
import { helsinkiToday } from '../../app/fundraising';


/** Slim bar above the public header; see docs/design-system/components/FundraisingBar.md. */
export function FundraisingBar({ bar, fundraisingUrl, text }: {
  bar: FundraisingBarConfig; fundraisingUrl: string; text: FundraisingBarText;
}) {
  const [today, setToday] = useState(bar.today);
  const [dismissed, setDismissed] = useState(false);
  const phase = barPhase(bar, today);
  const milestone = barMilestone(bar, today);

  useEffect(() => {
    const fresh = helsinkiToday();
    setToday(fresh);
    // A tab left open over midnight moves to the next phase, or hides after the end date.
    const timer = window.setInterval(() => setToday(helsinkiToday()), 60_000);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    try { setDismissed(isDismissed(window.localStorage.getItem(BAR_STORAGE_KEY), milestone, Date.now())); } catch { /* Storage can be blocked. */ }
  }, [milestone]);
  const visible = Boolean(phase) && !dismissed;
  useEffect(() => {
    document.documentElement.toggleAttribute('data-fb-hidden', !visible);
  }, [visible]);
  if (!visible || !phase || !bar.start || !bar.end) return null;

  function close() {
    try { window.localStorage.setItem(BAR_STORAGE_KEY, JSON.stringify({ at: Date.now(), milestone })); } catch { /* Dismissal then lasts for this page only. */ }
    setDismissed(true);
    document.querySelector<HTMLElement>('.public-site-header .logo')?.focus();
  }
  const open = phase === 'open';
  const long = open ? text.openUntil.replace('{date}', shortDate(bar.end)) : text.opens.replace('{date}', shortDate(bar.start));
  const short = open ? text.openShort : long;
  return <aside className="fundraising-bar" aria-label={text.label} lang="fi">
    <div className="fundraising-bar__inner">
      <p className="fundraising-bar__text">
        <span className="fundraising-bar__long">{long}</span><span className="fundraising-bar__short">{short}</span>
      </p>
      <div className="fundraising-bar__actions">
        <a className={`fundraising-bar__button ${open ? 'fundraising-bar__button--ghost' : 'fundraising-bar__button--primary'}`} href={fundraisingUrl}>{text.readMore}</a>
        {open && <a className="fundraising-bar__button fundraising-bar__button--primary" href={`${fundraisingUrl}${DONATION_ANCHOR}`}>{text.donate}</a>}
      </div>
      <button className="fundraising-bar__close" type="button" aria-label={text.close} onClick={close}>
        <i className="fas fa-times" aria-hidden="true" />
      </button>
    </div>
  </aside>;
}
