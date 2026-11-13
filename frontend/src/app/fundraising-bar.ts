/**
 * The always-on fundraising bar above the public header.
 *
 * Timing comes from the fundraising configuration (start and end date, shown
 * dates when unconfirmed), never from a constant here. The Flask session answer
 * carries `fundraising_bar`; this module only decides which phase applies on a
 * given Helsinki date and how a dismissal is remembered.
 */
import { helsinkiToday } from './fundraising';

export type FundraisingBarConfig = {
  /** The `show_bar` flag in the fundraising configuration. Off by default. */
  enabled: boolean;
  start: string | null;
  end: string | null;
  /** Details confirmed and the collection active: the date-independent part of `can_donate`. */
  donationsOpen: boolean;
  /** Helsinki date at the time the server built the answer, so hydration matches. */
  today: string;
};

export type FundraisingBarText = {
  label: string; opens: string; openUntil: string; openShort: string;
  readMore: string; donate: string; close: string;
};

export type BarPhase = 'pre' | 'open';
/** A dismissal ends early when the milestone changes. */
export type BarMilestone = 'pre' | 'open' | 'last';

export const disabledBar: FundraisingBarConfig = { enabled: false, start: null, end: null, donationsOpen: false, today: '' };

/** Days a dismissal is remembered. */
export const DISMISS_DAYS = 7;
/** The last days of the collection are a milestone of their own. */
export const LAST_DAYS = 14;
export const BAR_STORAGE_KEY = 'moso-fundraising-bar';
/** Anchor of the donation block on the fundraising page. */
export const DONATION_ANCHOR = '#donate-title';

function isoDay(value: unknown): string | null {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const [y, m, d] = value.split('-').map(Number);
  const parsed = new Date(Date.UTC(y, m - 1, d));
  return parsed.getUTCFullYear() === y && parsed.getUTCMonth() === m - 1 && parsed.getUTCDate() === d ? value : null;
}

/** Reject anything that does not match the session contract; the bar then stays off. */
export function normalizeBar(value: unknown, now: Date = new Date()): FundraisingBarConfig {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return { ...disabledBar, today: helsinkiToday(now) };
  const raw = value as Record<string, unknown>;
  const start = isoDay(raw.start);
  const end = isoDay(raw.end);
  const valid = Boolean(start && end && start <= end);
  return {
    enabled: raw.enabled === true && valid,
    start: valid ? start : null,
    end: valid ? end : null,
    donationsOpen: raw.donations_open === true,
    today: helsinkiToday(now),
  };
}

/**
 * Before the start date the bar announces the opening. From the start date to
 * the end date, inclusive, it invites donations, but only when the collection is
 * confirmed and active: otherwise the page itself says it is still being
 * prepared and a bar claiming it is running would be wrong. Dates compare as
 * strings because Helsinki dates are zero-padded ISO.
 */
export function barPhase(bar: FundraisingBarConfig, today: string = bar.today): BarPhase | null {
  if (!bar.enabled || !bar.start || !bar.end || !isoDay(today)) return null;
  if (today < bar.start) return 'pre';
  if (today <= bar.end) return bar.donationsOpen ? 'open' : null;
  return null;
}

function addDays(day: string, days: number): string {
  const [y, m, d] = day.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

export function barMilestone(bar: FundraisingBarConfig, today: string = bar.today): BarMilestone | null {
  const phase = barPhase(bar, today);
  if (!phase) return null;
  if (phase === 'pre') return 'pre';
  return bar.end && today > addDays(bar.end, -LAST_DAYS) ? 'last' : 'open';
}

/** `2026-11-16` becomes `16.11.` (Finnish short date without leading zeros). */
export function shortDate(day: string): string {
  const [, m, d] = day.split('-').map(Number);
  return `${d}.${m}.`;
}

export type StoredDismissal = { at: number; milestone: string };

export function readDismissal(raw: string | null): StoredDismissal | null {
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as Partial<StoredDismissal> | null;
    return value && typeof value.at === 'number' && Number.isFinite(value.at) && typeof value.milestone === 'string'
      ? { at: value.at, milestone: value.milestone } : null;
  } catch {
    return null;
  }
}

/** True while the visitor's dismissal still applies. A new milestone ends it early. */
export function isDismissed(raw: string | null, milestone: BarMilestone | null, now: number): boolean {
  const stored = readDismissal(raw);
  if (!stored || !milestone || stored.milestone !== milestone) return false;
  const age = now - stored.at;
  return age >= 0 && age < DISMISS_DAYS * 86_400_000;
}

/**
 * Inline script for the document head. It runs before first paint and marks the
 * page when this visitor dismissed the bar, so the sticky bar is never painted
 * and then removed (which would shift the page up). Keep it in step with
 * `isDismissed`; a test compares them.
 */
export function dismissScript(milestone: BarMilestone): string {
  return `<script>try{var d=JSON.parse(localStorage.getItem('${BAR_STORAGE_KEY}')||'null');`
    + `if(d&&d.milestone==='${milestone}'&&Date.now()-d.at>=0&&Date.now()-d.at<${DISMISS_DAYS * 86_400_000})`
    + `document.documentElement.setAttribute('data-fb-hidden','')}catch(e){}</script>`;
}

export const BAR_STYLESHEET = '<link rel="stylesheet" href="/static/css/fundraising-bar.css?v=20261113-1">';
