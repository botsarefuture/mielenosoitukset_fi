/**
 * Dates and phase of the campaign page. Every date comes from the shared
 * fundraising configuration (`utils/data/fundraising.json`, served by the Go
 * API as `GET /api/fundraising/details`); no component hardcodes one. The phase
 * is computed from the Helsinki date on the server and passed down, so server
 * and client render the same markup and the page never shifts after loading.
 */

export type CampaignSchedule = {
  collectionStart: string; collectionEnd: string; campaignStart: string;
  openingDate: string; openingTime: string; openingCity: string; openingCityIn: string;
  marketingStart: string; marketingEnd: string;
  collectionNumber: string; area: string;
};

export type MilestoneKey = 'collectionOpens' | 'collectionEnds' | 'campaignStarts' | 'opening' | 'marketingWeek';
export type MilestoneState = 'done' | 'current' | 'next';
export type Milestone = {
  key: MilestoneKey; state: MilestoneState;
  /** First Helsinki date on which the milestone counts as reached. */
  from: string;
  /** The first upcoming milestone gets the "Seuraavaksi" label while none is under way. */
  upNext: boolean;
};

export type CampaignPhase = {
  /** Before the collection opens: reminder slot, "Tietoa keräyksestä" below "Mistä on kyse". */
  preLaunch: boolean;
  /** The collection is open today (opening day to closing day inclusive). */
  collectionOpen: boolean;
  /** The collection has closed. */
  collectionClosed: boolean;
  /** "Tietoa keräyksestä" moves above "Mistä on kyse" from the opening day. */
  collectionInfoFirst: boolean;
  milestones: Milestone[];
};

function isoDate(value: unknown): string | null {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const [year, month, day] = value.split('-').map(Number);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  return parsed.getUTCFullYear() === year && parsed.getUTCMonth() === month - 1 && parsed.getUTCDate() === day ? value : null;
}

const text = (value: unknown) => (typeof value === 'string' ? value.trim() : '');

/** The day after an ISO date. */
export function nextDay(iso: string): string {
  const [year, month, day] = iso.split('-').map(Number);
  return new Date(Date.UTC(year, month - 1, day + 1)).toISOString().slice(0, 10);
}

/** Bundled defaults mirror `fundraising.json`; the live configuration overrides them field by field. */
export const defaultSchedule: CampaignSchedule = {
  collectionStart: '2026-11-16', collectionEnd: '2027-02-15', campaignStart: '2027-03-01',
  openingDate: '2027-03-06', openingTime: '18.00', openingCity: 'Tampere', openingCityIn: 'Tampereella',
  marketingStart: '2027-05-03', marketingEnd: '2027-05-09',
  collectionNumber: 'RA/2026/1586', area: 'Koko Suomi Ahvenanmaata lukuun ottamatta',
};

/** The schedule from a configuration object; anything missing or malformed falls back per field. */
export function campaignSchedule(input: unknown, fallback: CampaignSchedule = defaultSchedule): CampaignSchedule {
  const data: Record<string, unknown> = input && typeof input === 'object' && !Array.isArray(input) ? input as Record<string, unknown> : {};
  return {
    collectionStart: isoDate(data.start_date) ?? isoDate(data.planned_start_date) ?? fallback.collectionStart,
    collectionEnd: isoDate(data.end_date) ?? isoDate(data.planned_end_date) ?? fallback.collectionEnd,
    campaignStart: isoDate(data.campaign_start_date) ?? fallback.campaignStart,
    openingDate: isoDate(data.opening_date) ?? fallback.openingDate,
    openingTime: /^\d{1,2}\.\d{2}$/.test(text(data.opening_time)) ? text(data.opening_time) : fallback.openingTime,
    openingCity: text(data.opening_city) || fallback.openingCity,
    openingCityIn: text(data.opening_city_in) || fallback.openingCityIn,
    marketingStart: isoDate(data.marketing_week_start) ?? fallback.marketingStart,
    marketingEnd: isoDate(data.marketing_week_end) ?? fallback.marketingEnd,
    collectionNumber: text(data.collection_number) || fallback.collectionNumber,
    area: text(data.area) || fallback.area,
  };
}

/**
 * The phase for a Helsinki date (`YYYY-MM-DD`). A milestone is reached on its
 * first day; the closing milestone starts the day after the last collection day
 * because donations are still possible on it. The latest reached milestone is
 * "current" until the next one is reached, and the marketing week stops being
 * current the day after it ends.
 */
export function campaignPhase(schedule: CampaignSchedule, today: string): CampaignPhase {
  const starts: [MilestoneKey, string][] = [
    ['collectionOpens', schedule.collectionStart],
    ['collectionEnds', nextDay(schedule.collectionEnd)],
    ['campaignStarts', schedule.campaignStart],
    ['opening', schedule.openingDate],
    ['marketingWeek', schedule.marketingStart],
  ];
  const finished = today > schedule.marketingEnd;
  let current = -1;
  starts.forEach(([, from], index) => { if (from <= today) current = index; });
  if (finished) current = -1;
  const firstFuture = finished ? -1 : starts.findIndex(([, from]) => from > today);
  const milestones = starts.map(([key, from], index): Milestone => ({
    key, from,
    state: finished || index < current ? 'done' : index === current ? 'current' : 'next',
    upNext: current === -1 && index === firstFuture,
  }));
  const open = today >= schedule.collectionStart && today <= schedule.collectionEnd;
  return {
    preLaunch: today < schedule.collectionStart,
    collectionOpen: open,
    collectionClosed: today > schedule.collectionEnd,
    collectionInfoFirst: today >= schedule.collectionStart,
    milestones,
  };
}

/** `2026-11-16` -> `16.11.2026`. */
export const fiDate = (iso: string) => iso.split('-').reverse().map(Number).join('.');
/** `2026-11-16` -> `16.11.`. */
export const fiDayMonth = (iso: string) => fiDate(iso).replace(/\.\d{4}$/, '.');
/** `2027-05-03`, `2027-05-09` -> `3.–9.5.2027`. */
export function fiRange(start: string, end: string, withYear = true): string {
  const [, sm, sd] = start.split('-').map(Number);
  const [ey, em, ed] = end.split('-').map(Number);
  const tail = withYear ? `${em}.${ey}` : `${em}.`;
  return sm === em ? `${sd}.–${ed}.${tail}` : `${sd}.${sm}.–${ed}.${tail}`;
}
const weekdays = ['sunnuntai', 'maanantai', 'tiistai', 'keskiviikko', 'torstai', 'perjantai', 'lauantai'];
/** Weekday word of an ISO date in Finnish, lower case. */
export function fiWeekday(iso: string): string {
  const [year, month, day] = iso.split('-').map(Number);
  return weekdays[new Date(Date.UTC(year, month - 1, day)).getUTCDay()];
}
/** Essive of a weekday: `lauantai` -> `lauantaina`. */
export const fiWeekdayEssive = (iso: string) => `${fiWeekday(iso)}na`;
/** Two-letter weekday abbreviation: `La`. */
export const fiWeekdayShort = (iso: string) => { const w = fiWeekday(iso); return w[0].toUpperCase() + w[1]; };
