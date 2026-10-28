import { useEffect, useRef, useState } from 'react';
import { eventHref, internalHref } from '../listings/DemonstrationCard';
import type { Demonstration } from '../listings/types';

type Point = [number, number];
type MapInstance = {
  fitBounds(points: Point[], options: { padding: Point; maxZoom: number }): void;
  setView(point: Point, zoom: number): void;
  invalidateSize(): void;
  remove(): void;
};
type Group = { addTo(map: MapInstance): Group; clearLayers(): void };
type Tiles = { addTo(map: MapInstance): Tiles; on(name: string, handler: () => void): Tiles; redraw(): void };
type Marker = {
  bindPopup(content: HTMLElement): Marker; addTo(group: Group): Marker;
  getElement(): SVGElement | undefined; openPopup(): Marker; closePopup(): Marker;
};
type Leaflet = {
  map(node: HTMLElement, options: { center: Point; zoom: number; scrollWheelZoom: boolean }): MapInstance;
  tileLayer(url: string, options: { attribution: string; maxZoom: number }): Tiles;
  layerGroup(): Group;
  circleMarker(point: Point, options: { radius: number; color: string; fillColor: string; fillOpacity: number; weight: number }): Marker;
};
type MapMessages = {
  title: string; loading: string; error: string; retry: string; empty: string; noCoordinates: string;
  tileError: string; popupDetails: string; summary: string; zoomIn: string; zoomOut: string; mapLabel: string;
};
export type PrideMapProps = {
  endpoint: string; detailUrl: string; seriesUrl: string; locale: string; tag: 'pride'; messages: MapMessages;
};
type MapPage = { page: number; total_pages: number; total: number; results: Demonstration[] };
type Loaded = { events: Demonstration[]; cities: number; mapped: number };
const INITIAL_CENTER: Point = [64.5, 26.0];

function parsePage(value: unknown, expectedPage: number): MapPage {
  if (!value || typeof value !== 'object') throw new Error('Invalid Pride map response');
  const page = value as MapPage;
  if (!Number.isSafeInteger(page.page) || page.page !== expectedPage
    || !Number.isSafeInteger(page.total_pages) || page.total_pages < 1
    || !Number.isSafeInteger(page.total) || page.total < 0
    || !Array.isArray(page.results) || page.results.length > 100
    || !page.results.every(row => row && typeof row === 'object' && typeof row._id === 'string' && row._id.trim())) {
    throw new Error('Invalid Pride map page');
  }
  if (expectedPage === 1 && page.total_pages > Math.max(1, page.total)) throw new Error('Invalid Pride map bounds');
  return page;
}

function coordinate(value: unknown, limit: number): number | null {
  if (typeof value === 'string') {
    value = value.trim();
    if (!value || !/^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/.test(value as string)) return null;
    value = Number(value);
  }
  return typeof value === 'number' && Number.isFinite(value) && Math.abs(value) <= limit ? value : null;
}
function pointFor(event: Demonstration): Point | null {
  const latitude = coordinate(event.latitude, 90);
  const longitude = coordinate(event.longitude, 180);
  return latitude === null || longitude === null ? null : [latitude, longitude];
}
function publicText(value: unknown): string { return typeof value === 'string' ? value : ''; }

/** Leaflet owns only this canvas and its plain-text popup nodes, never the React listing. */
export function PrideMap(props: PrideMapProps) {
  const canvas = useRef<HTMLDivElement>(null);
  const reload = useRef<(() => void) | null>(null);
  const [pending, setPending] = useState(true);
  const [error, setError] = useState(false);
  const [tileError, setTileError] = useState(false);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const text = props.messages;

  useEffect(() => {
    let disposed = false;
    let busy = false;
    let request: AbortController | null = null;
    let frame: number | null = null;
    const availableLibrary = (window as Window & { L?: Leaflet }).L;
    if (!availableLibrary || !canvas.current) {
      // A page reload retries the local library too, rather than exposing an inert action.
      reload.current = () => window.location.reload();
      setPending(false); setError(true);
      return () => { reload.current = null; };
    }
    const library = availableLibrary;
    const map = library.map(canvas.current, { center: INITIAL_CENTER, zoom: 5, scrollWheelZoom: false });
    const markers = library.layerGroup().addTo(map);
    const tiles = library.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors', maxZoom: 19,
    }).on('tileerror', () => { if (!disposed) setTileError(true); }).addTo(map);
    const zoomIn = canvas.current.querySelector('.leaflet-control-zoom-in');
    const zoomOut = canvas.current.querySelector('.leaflet-control-zoom-out');
    zoomIn?.setAttribute('title', text.zoomIn); zoomIn?.setAttribute('aria-label', text.zoomIn);
    zoomOut?.setAttribute('title', text.zoomOut); zoomOut?.setAttribute('aria-label', text.zoomOut);

    function popup(event: Demonstration) {
      const content = document.createElement('div');
      const title = document.createElement('strong');
      title.textContent = publicText(event.title) || text.title;
      content.append(title);
      const detail = [publicText(event.formatted_date) || publicText(event.date_display) || publicText(event.date),
        [publicText(event.address), publicText(event.city)].filter(Boolean).join(', ')].filter(Boolean);
      detail.forEach(value => {
        const paragraph = document.createElement('p'); paragraph.textContent = value; content.append(paragraph);
      });
      const link = document.createElement('a');
      // Use the normal internal event URL rules; malformed/external URLs get a useful local fallback.
      const href = eventHref(event, props);
      link.href = href === '#' ? internalHref(props.detailUrl.replace('__ID__', encodeURIComponent(event._id))) : href;
      link.textContent = text.popupDetails; content.append(link);
      return content;
    }
    async function load() {
      if (disposed || busy) return;
      busy = true;
      request = new AbortController();
      const signal = request.signal;
      setPending(true); setError(false); setTileError(false);
      tiles.redraw();
      try {
        const events = new Map<string, Demonstration>();
        let pages = 1;
        for (let pageNumber = 1; pageNumber <= pages; pageNumber++) {
          const query = new URLSearchParams({ tag: props.tag, page: String(pageNumber), per_page: '100', lang: props.locale, scope: 'pride_map' });
          const response = await fetch(`${props.endpoint}?${query}`, { signal, credentials: 'same-origin', headers: { Accept: 'application/json' } });
          if (!response.ok || response.redirected) throw new Error('Pride map request failed');
          const page = parsePage(await response.json(), pageNumber);
          // This API is live, not a transactional snapshot. Later growth must not extend this traversal forever.
          if (pageNumber === 1) pages = page.total_pages;
          page.results.forEach(event => { if (!events.has(event._id)) events.set(event._id, event); });
        }
        if (disposed || signal.aborted) return;
        const rows = [...events.values()];
        const bounds: Point[] = [];
        const cities = new Set<string>();
        markers.clearLayers();
        rows.forEach(event => {
          const city = publicText(event.city).trim().toLocaleLowerCase(props.locale);
          if (city) cities.add(city);
          const point = pointFor(event);
          if (!point) return;
          const content = popup(event);
          const marker = library.circleMarker(point, {
            radius: 9, color: 'var(--pride-marker)', fillColor: 'var(--pride-marker-fill)', fillOpacity: .9, weight: 2,
          }).bindPopup(content).addTo(markers);
          const node = marker.getElement();
          if (node) {
            node.setAttribute('tabindex', '0');
            node.setAttribute('role', 'button');
            node.setAttribute('aria-label', [publicText(event.title) || text.title, publicText(event.city), text.popupDetails].filter(Boolean).join(', '));
            node.addEventListener('keydown', key => {
              if (key.key === 'Enter' || key.key === ' ') {
                key.preventDefault();
                marker.openPopup();
                content.querySelector('a')?.focus();
              }
            });
            content.addEventListener('keydown', key => {
              if (key.key === 'Escape') {
                key.preventDefault(); key.stopPropagation();
                marker.closePopup(); node.focus();
              }
            });
          }
          bounds.push(point);
        });
        if (bounds.length) map.fitBounds(bounds, { padding: [24, 24], maxZoom: 13 });
        else map.setView(INITIAL_CENTER, 5);
        frame = requestAnimationFrame(() => { if (!disposed) map.invalidateSize(); });
        setLoaded({ events: rows, cities: cities.size, mapped: bounds.length });
      } catch (reason) {
        if (!disposed && !signal.aborted) setError(true);
      } finally {
        busy = false;
        if (!disposed) setPending(false);
      }
    }
    reload.current = () => { void load(); };
    void load();
    return () => {
      disposed = true; request?.abort(); reload.current = null;
      if (frame !== null) cancelAnimationFrame(frame);
      map.remove();
    };
  }, [props.endpoint, props.detailUrl, props.seriesUrl, props.locale, props.tag, text]);

  const number = new Intl.NumberFormat(props.locale);
  const summary = loaded ? text.summary.replace('__EVENTS__', number.format(loaded.events.length))
    .replace('__CITIES__', number.format(loaded.cities)).replace('__MAPPED__', number.format(loaded.mapped)) : '';
  return <div className="pride-map-panel" aria-busy={pending}>
    <p id="pride-map-summary" className="pride-map-summary" role="status" aria-live="polite"
      hidden={!pending && !loaded} data-event-count={loaded?.events.length} data-city-count={loaded?.cities} data-mapped-count={loaded?.mapped}>
      {pending ? text.loading : summary}
    </p>
    <div id="pride-map-error" className="user-form-feedback user-form-feedback--error" hidden={!error}>
      <p role="alert">{text.error}</p>
    </div>
    <p className="pride-map-tile-warning" role="status" hidden={!tileError}>{text.tileError}</p>
    <button id="pride-map-retry" type="button" className="button button-secondary" disabled={pending}
      hidden={!error && !tileError} onClick={() => reload.current?.()}>{text.retry}</button>
    <div id="pride-map" className="pride-map-canvas" role="region" aria-label={text.mapLabel} tabIndex={0} ref={canvas} />
    <p id="pride-map-empty" role="status" hidden={!loaded || pending || !!loaded.mapped}>
      {loaded?.events.length ? text.noCoordinates : text.empty}
    </p>
  </div>;
}
