import { useEffect, useReducer, useState } from 'react';
import type { DetailEvent } from './types';
import { safeHref } from './content';

type State = { status: 'loading' } | { status: 'ready'; event: DetailEvent } | { status: 'error' } | { status: 'not-found' };
type StoredState = { key: string; value: State };
function text(value: unknown): string | null { return typeof value === 'string' ? value : null; }
function strings(value: unknown): string[] { return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []; }
function coordinate(value: unknown, maximum: number): number | null {
  return typeof value === 'number' && Number.isFinite(value) && Math.abs(value) <= maximum ? value : null;
}
export function parseDetail(value: unknown, expectedId: string): DetailEvent {
  if (!value || typeof value !== 'object') throw new Error('Invalid demonstration response');
  const data = value as Record<string, unknown>;
  if (data._id !== expectedId || typeof data.title !== 'string' || !data.title.trim()
      || typeof data.cancelled !== 'boolean' || !Array.isArray(data.tags) || !Array.isArray(data.organizers)) {
    throw new Error('Invalid demonstration response');
  }
  const result: DetailEvent = {
    _id: expectedId, title: data.title, description: text(data.description) ?? '', date: text(data.date),
    start_time: text(data.start_time), end_time: text(data.end_time), city: text(data.city), address: text(data.address),
    latitude: coordinate(data.latitude, 90), longitude: coordinate(data.longitude, 180), tags: strings(data.tags),
    route: strings(data.route), cancelled: data.cancelled, event_type: text(data.event_type), facebook: text(data.facebook),
    img: text(data.img), cover_picture: text(data.cover_picture), preview_image: text(data.preview_image), gallery_images: strings(data.gallery_images),
    organizers: [], cover_source: text(data.cover_source),
  };
  for (const raw of data.organizers) {
    if (!raw || typeof raw !== 'object') continue;
    const organizer = raw as Record<string, unknown>;
    if (typeof organizer.name !== 'string' && organizer.is_private !== true) continue;
    result.organizers.push({ name: text(organizer.name), email: text(organizer.email), logo: text(organizer.logo), is_private: organizer.is_private === true, website: text(organizer.website),
      organization_id: typeof organizer.organization_id === 'string' && /^[a-f\d]{24}$/i.test(organizer.organization_id) ? organizer.organization_id : null });
  }
  return result;
}

/** One data request per event/language, cancelled on route change or unmount. */
export function useDemonstration(endpoint: string, id: string, locale: string) {
  const key = `${endpoint}\n${id}\n${locale}`;
  const [revision, retry] = useReducer((value: number) => value + 1, 0);
  const [stored, setStored] = useState<StoredState>({ key, value: { status: 'loading' } });
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    let expired = false;
    setStored({ key, value: { status: 'loading' } });
    const timeout = window.setTimeout(() => { expired = true; controller.abort(); }, 10_000);
    async function load() {
      try {
        const base = safeHref(endpoint);
        if (!base || !/^[a-f\d]{24}$/i.test(id)) throw new Error('Invalid endpoint');
        const response = await fetch(`${base.replace(/\/$/, '')}/${encodeURIComponent(id)}?lang=${encodeURIComponent(locale)}`, {
          signal: controller.signal, credentials: 'omit', headers: { Accept: 'application/json' },
        });
        if (!active) return;
        if (response.status === 404) { setStored({ key, value: { status: 'not-found' } }); return; }
        if (!response.ok) throw new Error('Detail request failed');
        const event = parseDetail(await response.json(), id);
        if (active && !controller.signal.aborted) setStored({ key, value: { status: 'ready', event } });
      } catch {
        if (active && (!controller.signal.aborted || expired)) setStored({ key, value: { status: 'error' } });
      } finally { window.clearTimeout(timeout); }
    }
    void load();
    return () => { active = false; window.clearTimeout(timeout); controller.abort(); };
  }, [key, endpoint, id, locale, revision]);
  return { state: stored.key === key ? stored.value : { status: 'loading' } as State, retry };
}
