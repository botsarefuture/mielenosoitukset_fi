import catalogJSON from '../../../go-api/city_catalog.json?raw';
import { ttlCache } from './server-cache';

type CatalogCity = { key: string; name: string; phrase: string; default_enabled: boolean };
export type CitySummary = { key: string; name: string; phrase: string; demo_count: number; today_count: number; upcoming_count: number };
export type CitiesData = { day: string; cities: CitySummary[] };
export const cityCatalog: CatalogCity[] = JSON.parse(catalogJSON);
const byKey = new Map(cityCatalog.map(city => [city.key, city]));

export const cityKey = (value: string) => value.trim().normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
  .toLocaleLowerCase('fi').replace(/_/g, '-').split(/\s+/).join('-');
export const findCity = (value: string) => byKey.get(cityKey(value));
export const helsinkiDay = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Helsinki' }).format(new Date());
export const dayLabel = (day: string) => new Intl.DateTimeFormat('fi-FI', { dateStyle: 'long', timeZone: 'Europe/Helsinki' }).format(new Date(`${day}T12:00:00Z`));

/** Only explicit public fields reach the host's bootstrap document. */
export function readCities(value: unknown): CitiesData | null {
  if (!value || typeof value !== 'object') return null;
  const data = value as CitiesData;
  if (typeof data.day !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(data.day)
    || !Array.isArray(data.cities) || data.cities.length > cityCatalog.length) return null;
  const seen = new Set<string>();
  const cities: CitySummary[] = [];
  for (const row of data.cities) {
    const city = byKey.get(row?.key);
    if (!city || seen.has(row.key) || [row.demo_count, row.today_count, row.upcoming_count].some(n => !Number.isSafeInteger(n) || n < 0)) return null;
    seen.add(row.key);
    cities.push({ key: city.key, name: city.name, phrase: city.phrase, demo_count: row.demo_count,
      today_count: row.today_count, upcoming_count: row.upcoming_count });
  }
  return { day: data.day, cities };
}

const directory = ttlCache<CitiesData>(60_000, 4);
const pending = new Map<string, Promise<CitiesData | null>>();

export async function loadCities(readBase: string): Promise<CitiesData | null> {
  const key = `${readBase}\n${helsinkiDay()}`;
  const cached = directory.get(key);
  if (cached) return cached;
  if (pending.has(key)) return pending.get(key)!;
  if (pending.size >= 4) return null;
  const promise = (async () => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 1500);
    try {
      const response = await fetch(`${readBase}/cities`, { signal: controller.signal, credentials: 'omit', headers: { Accept: 'application/json' } });
      if (!response.ok) return null;
      const result = readCities(await response.json());
      if (result && !/no-store/i.test(response.headers.get('Cache-Control') ?? '')) directory.set(key, result);
      return result;
    } catch { return null; }
    finally { clearTimeout(timer); }
  })().finally(() => pending.delete(key));
  pending.set(key, promise);
  return promise;
}
