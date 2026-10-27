import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { flushSync } from 'react-dom';
import { DemonstrationCards } from './DemonstrationCard';
import type { ListingProps, ListParams, Page } from './types';

type LoadResult = { page: number; total_pages: number; deferred?: boolean };
type Options = { page?: number; append?: boolean; previous?: boolean; manual?: boolean };
type PageWindow = {
  first?: number; last?: number; range: { start: number; count: number }; reset(): void;
  canExtend(previous?: boolean, manual?: boolean): boolean;
  mount(page: Page, render: (container: HTMLElement) => Element[]): Element[];
};
type Controller = { reload(options: Options): Promise<LoadResult | null>; setState(page: number, total: number): void;
  resumeAuto(): void; destroy(): void };
type History = { params: ListParams; page: number; submit(): void; renderCities(): void;
  pageLoaded(page: Page): void; destroy(): void };
type ListingWindow = Window & {
  publicListWindow?: PageWindow; publicListHistory?: History; userPaginationController?: Controller;
  UserPagination: {
    createFilterHistory(options: { form: HTMLFormElement; fixed: Record<string, string>; cityLabel: string;
      removeLabel: string; onChange(params: ListParams, page: number): Promise<LoadResult | null> }): History;
    createLoadMoreController(options: { button: HTMLButtonElement; windowed: boolean;
      loadPage(page: number, options?: Options): Promise<LoadResult | null>; initialLabel: string; loadingLabel: string }): Controller;
  };
  publicCityAutocomplete(options: { cities: string[]; onSelect?: () => void }): void;
};

/** React owns each page's cards. The existing widget owns page wrappers/controls. */
export function attachListing(element: HTMLElement, props: ListingProps) {
  const globals = window as unknown as ListingWindow;
  const find = <T extends HTMLElement>(selector: string) => {
    const node = element.querySelector<T>(selector);
    if (!node) throw new Error(`Missing listing element: ${selector}`);
    return node;
  };
  const form = find<HTMLFormElement>('#search-form');
  const grid = find('#demos-grid');
  const more = find<HTMLButtonElement>('#load-more-btn');
  const summary = find('#listing-result-summary');
  const error = find('#listing-load-error');
  const retry = find<HTMLButtonElement>('#listing-load-error button');
  const empty = find('#no-results');
  const clear = find<HTMLButtonElement>('#clear-filters-btn');
  const roots = new Map<HTMLElement, Root>();
  let params: ListParams = {};
  let generation = 0;
  let appendGeneration: number | null = null;
  let request: AbortController | null = null;
  let lastFailure: { page: number; options: Options } | null = null;
  let destroyed = false;
  let controller: Controller;
  let history: History;
  function releaseRoots(all = false) {
    for (const [node, root] of roots) {
      if (all || !node.isConnected) { root.unmount(); roots.delete(node); }
    }
  }
  function parsePage(data: unknown): Page {
    if (!data || typeof data !== 'object') throw new Error('Invalid list response');
    const value = data as Page;
    if (!Array.isArray(value.results) || !value.results.every(row => row && typeof row._id === 'string')
      || !Number.isSafeInteger(value.page) || value.page < 1
      || !Number.isSafeInteger(value.total_pages) || value.total_pages < 1
      || !Number.isSafeInteger(value.total) || value.total < 0) throw new Error('Invalid list response');
    return { ...value, per_page: value.per_page || Number(params.per_page) || 12 };
  }
  async function load(page: number, options: Options = {}): Promise<LoadResult | null> {
    const { append = false, previous = false, manual = false } = options;
    const pageWindow = globals.publicListWindow!;
    if (destroyed || (append && !pageWindow.canExtend(previous, manual))) return null;
    if (!append) {
      generation++; request?.abort(); request = new AbortController(); appendGeneration = null;
      releaseRoots(true); pageWindow.reset();
      const loading = document.createElement('p');
      loading.className = 'loading-container'; loading.setAttribute('role', 'status');
      loading.textContent = props.messages.loading; grid.append(loading);
      empty.hidden = true; grid.hidden = false; summary.hidden = true;
    }
    const current = generation;
    if (append && appendGeneration === current) return null;
    if (append) appendGeneration = current;
    const signal = request!.signal;
    grid.setAttribute('aria-busy', 'true'); error.hidden = true;
    try {
      const query = new URLSearchParams(Object.entries({ ...params, page, lang: props.locale }).map(([key, value]) => [key, String(value)]));
      const response = await fetch(`${props.endpoint}?${query}`, { signal, credentials: 'same-origin', headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error('List request failed');
      const data = parsePage(await response.json());
      if (destroyed || current !== generation || signal.aborted) return null;
      if (append && !pageWindow.canExtend(previous, manual)) return { page: pageWindow.last!, total_pages: data.total_pages, deferred: true };
      if (!append) pageWindow.reset();
      pageWindow.mount(data, container => {
        const root = createRoot(container); roots.set(container, root);
        flushSync(() => root.render(<DemonstrationCards events={data.results} props={props} />));
        return Array.from(container.querySelectorAll('.demo-card'));
      });
      releaseRoots();
      const range = pageWindow.range;
      const number = new Intl.NumberFormat(props.locale);
      summary.textContent = props.messages.summary.replace('__START__', number.format(range.count ? range.start : 0))
        .replace('__END__', number.format(range.count ? range.start + range.count - 1 : 0))
        .replace('__COUNT__', number.format(data.total));
      summary.hidden = false;
      const filtered = ['search', 'location', 'date_start', 'date_end', ...(!props.fixed.city ? ['city'] : [])].some(key => params[key]);
      empty.hidden = range.count > 0; grid.hidden = !range.count;
      find('.no-results-text').textContent = filtered ? props.messages.filteredEmpty : props.messages.empty;
      clear.hidden = !filtered;
      history.pageLoaded(data); controller.setState(data.page, data.total_pages); lastFailure = null;
      return { page: data.page, total_pages: data.total_pages };
    } catch (reason) {
      if (destroyed || current !== generation || signal.aborted) return null;
      lastFailure = { page, options }; error.hidden = false;
      if (!append) grid.replaceChildren();
      return null;
    } finally {
      if (current === generation && !destroyed) grid.setAttribute('aria-busy', 'false');
      if (append && appendGeneration === current) appendGeneration = null;
    }
  }
  history = globals.UserPagination.createFilterHistory({ form, fixed: props.fixed,
    cityLabel: props.messages.city, removeLabel: props.messages.removeFilter,
    onChange(next, page) { params = next; return controller.reload({ page, append: false }); },
  });
  params = history.params; globals.publicListHistory = history;
  controller = globals.UserPagination.createLoadMoreController({ button: more, windowed: true,
    loadPage: load, initialLabel: props.messages.loadMore, loadingLabel: props.messages.loadingMore });
  globals.userPaginationController = controller;
  function submit(event: Event) { event.preventDefault(); history.submit(); }
  function clearFilters() {
    ['search', 'city', 'location', 'date_start', 'date_end', 'display_date_start', 'display_date_end'].forEach(name => {
      // Date display IDs also match hidden-field names; namedItem can return a RadioNodeList.
      const input = form.querySelector<HTMLInputElement>(`input[name="${name}"]`);
      if (input && !(props.fixed.city && name === 'city')) { input.value = ''; delete input.dataset.invalidDateEntry; }
    });
    history.submit();
  }
  async function retryFailure() {
    if (!lastFailure || retry.disabled) return;
    retry.disabled = true;
    try {
      const result = await load(lastFailure.page, { ...lastFailure.options, manual: true });
      if (result) controller.resumeAuto();
    } finally { retry.disabled = false; }
  }
  form.addEventListener('submit', submit); clear.addEventListener('click', clearFilters); retry.addEventListener('click', retryFailure);
  globals.publicCityAutocomplete({ cities: props.cities, onSelect: props.fixed.tag ? () => history.submit() : undefined });
  void controller.reload({ page: history.page, append: false });
  return () => {
    destroyed = true; generation++; request?.abort(); controller.destroy(); history.destroy();
    form.removeEventListener('submit', submit); clear.removeEventListener('click', clearFilters); retry.removeEventListener('click', retryFailure);
    // Outer-root disposal may itself be in React's commit; dispose nested roots after it.
    queueMicrotask(() => releaseRoots(true));
    if (globals.userPaginationController === controller) delete globals.userPaginationController;
    if (globals.publicListHistory === history) delete globals.publicListHistory;
    delete globals.publicListWindow;
  };
}
