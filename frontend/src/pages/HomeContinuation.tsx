import { useCallback, useEffect, useRef, useState } from 'react';
import { DemonstrationCards } from '../components/listings/DemonstrationCard';
import type { CardProps } from '../components/listings/DemonstrationCard';
import type { Demonstration, Page } from '../components/listings/types';

export type HomeContinuationProps = {
  /** Public Go listing endpoint (`/api/demonstrations`). */
  endpoint: string; locale: string; cards: CardProps;
  /** Real listing URL: the no-JS, keyboard and crawler path to every event. */
  allUrl: string;
  /** Events already shown in the picks above, so the continuation never repeats them. */
  shownIds: string[];
  text: { title: string; intro: string; loading: string; loaded: string; loadMore: string;
    loadError: string; retry: string; all: string; end: string };
};

/** Pages loaded on scroll before the visitor has to ask, so the footer and the
 * campaign below stay reachable instead of being pushed away forever. */
export const AUTO_PAGES = 2;
const PER_PAGE = 12;
/** Pages skipped in one request chain when every row duplicates the picks. */
const MAX_SKIPPED_PAGES = 3;

type Batch = { page: number; events: Demonstration[] };
type Status = 'idle' | 'loading' | 'error' | 'done';

function parsePage(data: unknown): Page {
  const value = data as Page;
  if (!value || !Array.isArray(value.results) || value.results.length > 100
    || !value.results.every(row => row && typeof row._id === 'string' && typeof row.title === 'string')
    || !Number.isSafeInteger(value.page) || value.page < 1
    || !Number.isSafeInteger(value.total_pages) || value.total_pages < 1) throw new Error('Invalid list response');
  return value;
}

/**
 * Continues the home picks with the chronological public listing. The first
 * pages load as the visitor scrolls towards them; afterwards a button and the
 * real `/demonstrations` link take over. Data comes from the same public Go
 * contract as the listing page, so no new server surface is needed.
 */
export function HomeContinuation({ endpoint, locale, cards, allUrl, shownIds, text }: HomeContinuationProps) {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [status, setStatus] = useState<Status>('idle');
  const [announcement, setAnnouncement] = useState('');
  const next = useRef(1);
  const seen = useRef(new Set(shownIds));
  const autoLeft = useRef(AUTO_PAGES);
  const busy = useRef(false);
  const focusFirst = useRef<string | null>(null);
  const sentinel = useRef<HTMLDivElement>(null);
  const request = useRef<AbortController | null>(null);

  // Picks arrive after hydration when the server had no batch: never repeat them.
  useEffect(() => { for (const id of shownIds) seen.current.add(id); }, [shownIds]);

  const load = useCallback(async (manual: boolean) => {
    if (busy.current) return;
    busy.current = true;
    if (!manual) autoLeft.current--;
    setStatus('loading'); setAnnouncement(text.loading);
    const controller = new AbortController();
    request.current = controller;
    try {
      let fresh: Demonstration[] = [];
      let page = next.current;
      let total = page;
      for (let skipped = 0; ; skipped++) {
        const url = new URL(endpoint, window.location.origin);
        url.search = new URLSearchParams({ page: String(page), per_page: String(PER_PAGE), lang: locale }).toString();
        const response = await fetch(url, { signal: controller.signal, credentials: 'omit', headers: { Accept: 'application/json' } });
        if (!response.ok) throw new Error('List request failed');
        const data = parsePage(await response.json());
        total = data.total_pages;
        fresh = data.results.filter(event => !seen.current.has(event._id));
        page++;
        if (fresh.length || page > total || skipped >= MAX_SKIPPED_PAGES) break;
      }
      if (controller.signal.aborted) return;
      for (const event of fresh) seen.current.add(event._id);
      next.current = page;
      if (fresh.length) {
        if (manual) focusFirst.current = fresh[0]._id;
        setBatches(current => [...current, { page: page - 1, events: fresh }]);
      }
      const finished = page > total;
      setStatus(finished ? 'done' : 'idle');
      setAnnouncement(`${text.loaded.replace('__COUNT__', String(fresh.length))}${finished ? ` ${text.end}` : ''}`);
    } catch {
      if (controller.signal.aborted) return;
      setStatus('error'); setAnnouncement(text.loadError);
    } finally {
      busy.current = false;
    }
  }, [endpoint, locale, text]);

  useEffect(() => () => request.current?.abort(), []);

  // Keyboard users who asked for more land on the first new card, not back at the top.
  useEffect(() => {
    const id = focusFirst.current;
    if (!id) return;
    focusFirst.current = null;
    document.querySelector<HTMLElement>(`.home-more-grid [data-demo-id="${CSS.escape(id)}"]`)?.focus();
  }, [batches]);

  // Scrolling near the end of the visible cards loads the next page by itself.
  useEffect(() => {
    const node = sentinel.current;
    if (!node || typeof IntersectionObserver === 'undefined' || status !== 'idle' || autoLeft.current <= 0) return;
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) void load(false);
    }, { rootMargin: '0px 0px 480px 0px' });
    observer.observe(node);
    return () => observer.disconnect();
  }, [status, batches, load]);

  const loading = status === 'loading';
  return <section className="home-more" aria-labelledby="home-more-title">
    <div className="home-more-intro">
      <h2 id="home-more-title">{text.title}</h2>
      <p>{text.intro}</p>
      <span className="home-more-cue" aria-hidden="true" />
    </div>
    {batches.length > 0 && <div className="demos-grid home-more-grid" aria-busy={loading}>
      {batches.map(batch => <div className="home-more-page" key={batch.page}>
        <DemonstrationCards events={batch.events} props={cards} />
      </div>)}
    </div>}
    {loading && <div className="demos-grid home-more-skeleton" aria-hidden="true">
      {[0, 1, 2].map(index => <div key={index} className="home-more-placeholder" />)}
    </div>}
    <div ref={sentinel} className="home-more-sentinel" />
    <p className="home-more-status" role="status">{announcement}</p>
    <div className="home-more-next">
      {status === 'error' ? <>
        <p className="home-more-error">{text.loadError}</p>
        <button type="button" className="home-button" onClick={() => void load(true)}>{text.retry}</button>
      </> : status !== 'done' && <button type="button"
        className="home-button home-more-button" disabled={loading} onClick={() => void load(true)}>{text.loadMore}</button>}
      {status === 'done' && <p className="home-more-end">{text.end}</p>}
      <a className="home-button home-button--secondary" href={allUrl}>{text.all} <span aria-hidden="true">→</span></a>
    </div>
  </section>;
}
