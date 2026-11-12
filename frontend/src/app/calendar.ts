import { ttlCache } from './server-cache';
import { findCity, helsinkiDay } from './cities';
import type { Page } from '../components/listings/types';

export type CalendarMonth = { year: number; month: number; city?: string };
export type CalendarData = CalendarMonth & { total: number; days: { date: string; count: number }[] };
export type CalendarBootstrap = CalendarMonth & { data: CalendarData | null; day: number; page: number; events?: Page | null };
export const monthPath = ({ year, month, city }: CalendarMonth) => `${city ? `/city/${city}/calendar` : '/calendar'}/${year}/${month ? `${month}/` : ''}`;
export const calendarPlace = (period: CalendarMonth) => period.city ? findCity(period.city)?.phrase ?? period.city : 'Suomessa';
export const monthName = ({ year, month }: CalendarMonth) => new Intl.DateTimeFormat('fi-FI', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(Date.UTC(year, month - 1, 1)));
export const monthLength = ({ year, month }: CalendarMonth) => new Date(Date.UTC(year, month, 0)).getUTCDate();
export const dateForDay = (month: CalendarMonth, day: number) => `${month.year}-${String(month.month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
export function currentMonth(): CalendarMonth {
  const [year, month] = helsinkiDay().split('-').map(Number);
  return { year, month };
}
export function adjacentMonth(month: CalendarMonth, offset: number): CalendarMonth {
  const date = new Date(Date.UTC(month.year, month.month - 1 + offset, 1));
  return { year: date.getUTCFullYear(), month: date.getUTCMonth() + 1, ...(month.city ? { city: month.city } : {}) };
}
export function readCalendar(value: unknown, month: CalendarMonth): CalendarData | null {
  if (!value || typeof value !== 'object') return null;
  const data = value as CalendarData;
  if (data.year !== month.year || data.month !== month.month || (data.city ?? '') !== (month.city ?? '') || !Number.isSafeInteger(data.total) || data.total < 0 || !Array.isArray(data.days) || data.days.length > (month.month ? 31 : 366)) return null;
  let previous = '';
  let total = 0;
  for (const row of data.days) {
    if (!row || typeof row.date !== 'string' || row.date <= previous || !Number.isSafeInteger(row.count) || row.count < 1) return null;
    const date = new Date(`${row.date}T00:00:00Z`);
    if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0,10) !== row.date || date.getUTCFullYear() !== month.year || (month.month && date.getUTCMonth()+1 !== month.month)) return null;
    previous = row.date; total += row.count;
  }
  return total === data.total ? data : null;
}
export function selectedDay(month: CalendarMonth, data: CalendarData | null, search: string): number {
  const value = new URLSearchParams(search).get('day');
  const day = value && /^\d{1,2}$/.test(value) ? Number(value) : 0;
  if (day >= 1 && day <= monthLength(month)) return day;
  const today = helsinkiDay();
  if (today.slice(0, 7) === dateForDay(month, 1).slice(0, 7)) return Number(today.slice(8));
  return data?.days.length ? Number(data.days[0].date.slice(8)) : 1;
}

const months = ttlCache<CalendarData>(60_000, 64);
const pending = new Map<string, Promise<CalendarData | null>>();
export async function loadCalendar(base: string, month: CalendarMonth): Promise<CalendarData | null> {
  const key = `${base}/calendar/${month.year}${month.month ? `/${month.month}` : ''}${month.city ? `?city=${encodeURIComponent(month.city)}` : ''}`;
  const cached = months.get(key);
  if (cached) return cached;
  if (pending.has(key)) return pending.get(key)!;
  if (pending.size >= 8) return null;
  const request = (async () => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 1500);
    try {
      const response = await fetch(key, { signal: controller.signal, credentials: 'omit' });
      if (!response.ok) return null;
      const data = readCalendar(await response.json(), month);
      if (data && !/no-store/i.test(response.headers.get('Cache-Control') ?? '')) months.set(key, data);
      return data;
    } catch { return null; }
    finally { clearTimeout(timer); }
  })().finally(() => pending.delete(key));
  pending.set(key, request);
  return request;
}
