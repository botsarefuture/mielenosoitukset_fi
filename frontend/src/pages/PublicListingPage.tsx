import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import { DemonstrationCards } from '../components/listings/DemonstrationCard';
import { ListingTools } from '../components/listings/ListingTools';
import { displayDate, isoDate, ReactSearchFilters } from '../components/listings/ReactSearchFilters';
import type { ListingFilters } from '../components/listings/ReactSearchFilters';
import type { ListingProps, ListParams, Page } from '../components/listings/types';
import { FILTERS, listingQuery, QUERY_FILTERS } from '../components/listings/query';
import '../components/listings/react-listing.css';
import '../../../mielenosoitukset_fi/static/css/public-detail.css';

export type PublicListingProps = ListingProps & {
  /** Optional notice shown between the tools and the results. */
  notice?: ReactNode;
  initialData?: Page | null;
  initialSearch?: string;
  /** Deliberate first-page searches, independent of the public content cache. */
  onSearch?: (search: string) => void;
};

const MAX_PAGES = 5;

function formValues(params: ListParams): ListingFilters {
  return {
    search: String(params.search ?? ''), city: String(params.city ?? '').split(',').map(city => city.trim()).filter(Boolean).join(','), location: String(params.location ?? ''),
    date_start: displayDate(String(params.date_start ?? '')), date_end: displayDate(String(params.date_end ?? '')),
  };
}

function parsePage(value: unknown): Page {
  if (!value || typeof value !== 'object') throw new Error('Invalid list response');
  const data = value as Page;
  if (!Array.isArray(data.results) || data.results.length > 100
    || !data.results.every(row => row && typeof row._id === 'string')
    || !Number.isSafeInteger(data.page) || data.page < 1
    || !Number.isSafeInteger(data.per_page) || data.per_page < 1 || data.per_page > 100
    || !Number.isSafeInteger(data.total_pages) || data.total_pages < 1
    || !Number.isSafeInteger(data.total) || data.total < 0) throw new Error('Invalid list response');
  return data;
}

type LoadOptions = { params: ListParams; page: number; append?: boolean; previous?: boolean; manual?: boolean; history?: 'push' | 'replace' };

/** React owns filters, URL history, bounded page batches and every card. */
export function PublicListingPage(props: PublicListingProps) {
  const initial = useRef(listingQuery(props.initialSearch ?? window.location.search, props.fixed)).current;
  const [values, setValues] = useState(() => formValues(initial.params));
  const [params, setParams] = useState(initial.params);
  const [pages, setPages] = useState<Page[]>(() => props.initialData ? [props.initialData] : []);
  const [loading, setLoading] = useState(!props.initialData);
  const [failure, setFailure] = useState<LoadOptions | null>(null);
  const [column, setColumn] = useState(1);
  const grid = useRef<HTMLDivElement>(null);
  const more = useRef<HTMLButtonElement>(null);
  const previous = useRef<HTMLButtonElement>(null);
  const request = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const loadingRef = useRef(false);
  const pagesRef = useRef(pages);
  const paramsRef = useRef(params);
  const failureRef = useRef(failure);
  const scrollHost = useRef<HTMLElement | Window>(window);
  const anchor = useRef<{ node: Element; top: number } | null>(null);
  const latestSearch = useRef(props.onSearch);
  latestSearch.current = props.onSearch;
  pagesRef.current = pages; paramsRef.current = params; failureRef.current = failure;

  function writeHistory(next: ListParams, page: number, mode: 'push' | 'replace') {
    const url = new URL(window.location.href);
    for (const name of [...QUERY_FILTERS, ...Object.keys(props.fixed), 'page', 'per_page', 'display_date_start', 'display_date_end']) url.searchParams.delete(name);
    for (const [key, value] of Object.entries(next)) if (String(value)) url.searchParams.set(key, String(value));
    url.searchParams.set('page', String(page));
    if (mode === 'push' && url.href !== window.location.href) window.history.pushState({}, '', url);
    else window.history.replaceState(window.history.state, '', url);
  }

  function canExtend(back: boolean, manual: boolean) {
    const current = pagesRef.current;
    if (current.length < MAX_PAGES) return true;
    const edge = back ? current[current.length - 1] : current[0];
    const node = grid.current?.querySelector(`[data-list-page="${edge.page}"]`);
    if (!node || node.contains(document.activeElement)) return false;
    const boxes = [...node.children].map(child => child.getBoundingClientRect());
    const viewport = scrollHost.current instanceof Window ? { top: 0, bottom: window.innerHeight }
      : scrollHost.current.getBoundingClientRect();
    return manual || (back ? boxes.every(box => box.top > viewport.bottom) : boxes.every(box => box.bottom < viewport.top));
  }

  async function load(options: LoadOptions) {
    if (options.append && (loadingRef.current || !canExtend(Boolean(options.previous), Boolean(options.manual)))) return;
    if (!options.append) {
      generation.current++; request.current?.abort(); request.current = new AbortController();
      setPages([]); setParams(options.params); paramsRef.current = options.params;
    }
    const current = generation.current;
    const signal = request.current!.signal;
    loadingRef.current = true; setLoading(true); setFailure(null);
    try {
      const query = new URLSearchParams(Object.entries({ ...options.params, page: options.page, lang: props.locale })
        .map(([name, value]) => [name, String(value)]));
      const response = await fetch(`${props.endpoint}?${query}`, { signal, credentials: 'omit', headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error('List request failed');
      const data = parsePage(await response.json());
      if (signal.aborted || current !== generation.current) return;
      if (options.append) {
        if (!canExtend(Boolean(options.previous), Boolean(options.manual))) return;
        const batches = pagesRef.current;
        const surviving = options.previous ? batches[0] : batches[batches.length - 1];
        const node = grid.current?.querySelector(`[data-list-page="${surviving?.page}"] > .demo-card`);
        if (node) anchor.current = { node, top: node.getBoundingClientRect().top };
        setPages(old => {
          if (old.some(batch => batch.page === data.page)) return old;
          const next = options.previous ? [data, ...old] : [...old, data];
          return options.previous ? next.slice(0, MAX_PAGES) : next.slice(-MAX_PAGES);
        });
      } else setPages([data]);
      writeHistory(options.params, data.page, options.history ?? 'replace');
    } catch {
      if (!signal.aborted && current === generation.current) setFailure(options);
    } finally {
      if (current === generation.current && !signal.aborted) { loadingRef.current = false; setLoading(false); }
    }
  }
  const latestLoad = useRef(load);
  latestLoad.current = load;

  useEffect(() => {
    request.current = new AbortController();
    const start = listingQuery(props.initialSearch ?? window.location.search, props.fixed);
    if (props.initialData) writeHistory(start.params, props.initialData.page, 'replace');
    else void latestLoad.current({ ...start, history: 'replace' });
    if (start.page === 1 && String(start.params.search ?? '').trim().length >= 2) latestSearch.current?.(String(start.params.search));
    function restore() {
      const next = listingQuery(window.location.search, props.fixed);
      setValues(formValues(next.params));
      void latestLoad.current({ ...next, history: 'replace' });
    }
    window.addEventListener('popstate', restore);
    return () => { generation.current++; request.current?.abort(); window.removeEventListener('popstate', restore); };
  }, [props.endpoint, props.locale, JSON.stringify(props.fixed)]);

  useLayoutEffect(() => {
    const element = grid.current;
    if (!element) return;
    for (let node = element.parentElement; node; node = node.parentElement) {
      if (node !== document.scrollingElement && /auto|scroll/.test(getComputedStyle(node).overflowY)) { scrollHost.current = node; break; }
    }
    const update = () => {
      // A column from the wider layout must not create implicit tracks while
      // measuring the new responsive grid after a resize.
      element.style.removeProperty('--public-list-first-column');
      const columns = getComputedStyle(element).gridTemplateColumns.split(/\s+/).filter(Boolean).length || 1;
      const start = pagesRef.current[0]?.result_start || 1;
      const next = (start - 1) % columns + 1;
      element.style.setProperty('--public-list-first-column', String(next));
      setColumn(next);
    };
    update();
    const observer = new ResizeObserver(update); observer.observe(element);
    if (anchor.current?.node.isConnected) {
      scrollHost.current.scrollBy({ top: anchor.current.node.getBoundingClientRect().top - anchor.current.top, behavior: 'instant' });
    }
    anchor.current = null;
    return () => observer.disconnect();
  }, [pages]);

  useEffect(() => {
    if ((navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData) return;
    let frame: number | null = null;
    let lastPosition = 0;
    let backwards = false;
    const position = () => scrollHost.current instanceof Window ? window.scrollY : scrollHost.current.scrollTop;
    function check() {
      frame = null;
      if (loadingRef.current || failureRef.current || !pagesRef.current.length) return;
      const button = backwards ? previous.current : more.current;
      if (!button || button.hidden || button === document.activeElement) return;
      const rect = button.getBoundingClientRect();
      const bounds = scrollHost.current instanceof Window ? { top: 0, bottom: innerHeight } : scrollHost.current.getBoundingClientRect();
      if (rect.top > bounds.bottom + 400 || rect.bottom < bounds.top - 400) return;
      const batches = pagesRef.current;
      const page = backwards ? batches[0].page - 1 : batches[batches.length - 1].page + 1;
      void latestLoad.current({ params: paramsRef.current, page, append: true, previous: backwards });
    }
    function scroll() {
      const next = position();
      if (next !== lastPosition) backwards = next < lastPosition;
      lastPosition = next;
      if (frame === null) frame = requestAnimationFrame(check);
    }
    const host = scrollHost.current;
    lastPosition = position();
    host.addEventListener('scroll', scroll, { passive: true });
    frame = requestAnimationFrame(check);
    return () => { host.removeEventListener('scroll', scroll); if (frame !== null) cancelAnimationFrame(frame); };
  }, [pages]);

  function submit(next: ListingFilters, reset = false) {
    const nextParams: ListParams = { ...(reset ? {} : params), per_page: params.per_page || 12 };
    for (const name of FILTERS) delete nextParams[name];
    for (const key of ['search', 'city', 'location'] as const) if (next[key].trim()) nextParams[key] = next[key].trim();
    const start = isoDate(next.date_start), end = isoDate(next.date_end);
    if (start) nextParams.date_start = start;
    if (end) nextParams.date_end = end;
    Object.assign(nextParams, props.fixed);
    setValues(formValues(nextParams));
    if (next.search.trim().length >= 2) latestSearch.current?.(next.search.trim());
    void load({ params: nextParams, page: 1, history: 'push' });
  }
  const clear = () => submit(formValues(props.fixed), true);
  const first = pages[0];
  const last = pages[pages.length - 1];
  const count = pages.reduce((total, batch) => total + batch.results.length, 0);
  const text = props.messages;
  const number = new Intl.NumberFormat(props.locale);
  const start = count ? first.result_start || (first.page - 1) * first.per_page + 1 : 0;
  const summary = text.summary.replace('__START__', number.format(start)).replace('__END__', number.format(count ? start + count - 1 : 0))
    .replace('__COUNT__', number.format(first?.total ?? 0));
  const filtered = QUERY_FILTERS.some(key => !props.fixed[key] && params[key]);
  const EmptyHeading = props.headingLevel === 2 ? 'h3' : 'h2';
  return <section className="public-demonstration-list public-react-list">
    {props.cover && <img className="public-list-cover" src={props.cover} alt={props.coverAlt} />}
    <ListingTools props={props} filters={<ReactSearchFilters props={props} values={values} change={setValues} submit={submit}
      removeCity={city => submit({ ...values, city: values.city.split(',').filter(value => value !== city).join(',') })} />} />
    {props.notice}
    <section className="public-list-results" aria-labelledby="listing-title">
      <button ref={previous} id="load-previous-btn" type="button" className="detail-button load-more"
        hidden={!first || first.page <= 1} disabled={loading}
        onClick={() => void load({ params, page: first.page - 1, append: true, previous: true, manual: true })}>{text.previous}</button>
      <div ref={grid} id="demos-grid" className="demos-grid public-list-window" aria-busy={loading}
        hidden={!loading && !count} style={{ '--public-list-first-column': column } as CSSProperties}>
        {pages.map(batch => <div key={batch.page} className="demos-grid public-list-page" data-list-page={batch.page}>
          <DemonstrationCards events={batch.results} props={props} />
        </div>)}
        {loading && !pages.length && <p className="loading-container" role="status">{text.loading}</p>}
      </div>
      <p id="listing-result-summary" className="public-listing-summary" role="status" aria-live="polite" aria-atomic="true" hidden={!first || !count}>{summary}</p>
      <div id="listing-load-error" className="public-listing-summary" hidden={!failure}>
        <p role="alert">{text.loadError}</p><button type="button" className="detail-button" disabled={loading}
          onClick={() => failure && void load({ ...failure, manual: true })}>{text.retry}</button>
      </div>
      <div id="no-results" className="no-results-card" hidden={loading || Boolean(failure) || count > 0}>
        <EmptyHeading className="no-results-title">{text.emptyTitle}</EmptyHeading><p className="no-results-text">{filtered ? text.filteredEmpty : text.empty}</p>
        <div className="no-results-action"><button type="button" id="clear-filters-btn" className="detail-button" hidden={!filtered} onClick={clear}>{text.clearFilters}</button>
          <a href={props.submitUrl} className="button button-primary">{text.submitEvent}</a></div>
      </div>
      <button ref={more} id="load-more-btn" type="button" className="detail-button load-more"
        hidden={!last || last.page >= last.total_pages || Boolean(failure)} disabled={loading}
        onClick={() => void load({ params, page: last.page + 1, append: true, manual: true })}>{loading ? text.loadingMore : text.loadMore}</button>
    </section>
  </section>;
}
