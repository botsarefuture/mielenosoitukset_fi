/**
 * Public fundraising details. A port of mielenosoitukset_fi/utils/fundraising.py:
 * incomplete or unconfirmed configuration never opens donations. Both versions
 * are checked against tests/fixtures/fundraising_parity.json.
 */
export type FundraisingDetails = {
  organizer: string; collection_number: string; recipient: string; iban: string; reference: string;
  payment_url: string;
  mobilepay_links: { label: string; url: string }[];
  start_date: string | null; end_date: string | null;
  display_start_date: string | null; display_end_date: string | null;
  confirmed: boolean; is_preparation: boolean; show_header_link: boolean; can_donate: boolean;
};

const TEXT_FIELDS = ['organizer', 'collection_number', 'recipient', 'iban', 'reference', 'payment_url'] as const;

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

/** Only a deliberately configured HTTPS destination without credentials becomes a link. */
export function httpsUrl(value: unknown): string {
  if (typeof value !== 'string') return '';
  const trimmed = value.trim();
  // Any whitespace or control character, or a backslash, is rejected outright.
  if (/[\s\u0000-\u001f\u007f\\]/.test(trimmed)) return '';
  const match = /^([A-Za-z][A-Za-z0-9+.-]*):\/\/([^/?#]*)/.exec(trimmed);
  if (!match || match[1].toLowerCase() !== 'https') return '';
  const authority = match[2];
  if (authority.includes('@')) return '';
  const host = /^(\[[^\]]*\]|[^:]*)(?::(\d*))?$/.exec(authority);
  if (!host || !host[1]) return '';
  if (host[2] !== undefined && host[2] !== '' && Number(host[2]) > 65535) return '';
  try {
    new URL(trimmed);
  } catch {
    return '';
  }
  return trimmed;
}

/** A strict `YYYY-MM-DD` calendar date, or null. */
function isoDate(value: unknown): string | null {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const [year, month, day] = value.split('-').map(Number);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  return parsed.getUTCFullYear() === year && parsed.getUTCMonth() === month - 1 && parsed.getUTCDate() === day ? value : null;
}

/**
 * The raw fundraising configuration from the Go API, or null when it is
 * unreachable or malformed; callers then use the copy bundled with the host.
 */
export async function loadFundraisingData(readBase: string): Promise<Record<string, unknown> | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 1500);
  try {
    const response = await fetch(`${readBase}/fundraising/details`, {
      signal: controller.signal, credentials: 'omit', headers: { Accept: 'application/json' },
    });
    if (!response.ok) return null;
    const data: unknown = await response.json();
    return data && typeof data === 'object' && !Array.isArray(data) ? data as Record<string, unknown> : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/** Today's date in Helsinki as `YYYY-MM-DD`. */
export function helsinkiToday(now = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Helsinki', year: 'numeric', month: '2-digit', day: '2-digit' }).format(now);
}

export function fundraisingDetails(input: unknown, today: string = helsinkiToday()): FundraisingDetails {
  const data: Record<string, unknown> = input && typeof input === 'object' && !Array.isArray(input) ? input as Record<string, unknown> : {};
  const fields = Object.fromEntries(TEXT_FIELDS.map(key => [key, text(data[key])])) as Record<typeof TEXT_FIELDS[number], string>;
  fields.payment_url = httpsUrl(fields.payment_url);
  const rawLinks = Array.isArray(data.mobilepay_links) ? data.mobilepay_links : [];
  const mobilepay_links = rawLinks.flatMap((entry, index) => {
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) return [];
    const record = entry as Record<string, unknown>;
    const label = record.label === undefined ? '' : record.label;
    if (typeof label !== 'string') return [];
    return [{ label: label.trim() || `MobilePay ${index + 1}`, url: httpsUrl(record.url) }];
  });
  let start = isoDate(data.start_date);
  let end = isoDate(data.end_date);
  if (!start || !end) start = end = null;
  let plannedStart = isoDate(data.planned_start_date);
  let plannedEnd = isoDate(data.planned_end_date);
  if (!plannedStart || !plannedEnd) plannedStart = plannedEnd = null;
  const complete = Boolean(start && end && start <= end && fields.organizer && fields.collection_number
    && (fields.payment_url || (fields.recipient && fields.iban) || mobilepay_links.some(link => link.url)));
  const confirmed = data.details_confirmed === true && complete;
  const state = data.publication_state;
  return {
    ...fields,
    mobilepay_links,
    start_date: start,
    end_date: end,
    confirmed,
    display_start_date: confirmed ? start : plannedStart,
    display_end_date: confirmed ? end : plannedEnd,
    is_preparation: !confirmed || (state !== 'active' && state !== 'closed'),
    show_header_link: data.show_header_link === true,
    can_donate: Boolean(confirmed && state === 'active' && start! <= today && today <= end!),
  };
}

/**
 * Page-only extras that are not part of the Flask parity rules: the bank's BIC,
 * the collection area, and the pre-launch state. The page is in pre-launch mode
 * while Helsinki's date is before the collection's first day, so it switches at
 * 00:00 Europe/Helsinki without a deploy. The opening day is the existing
 * `start_date` (or `planned_start_date`) value, not a second copy.
 */
export type FundraisingExtras = { bic: string; area: string; pre_launch: boolean; opens_date: string | null };

export function fundraisingExtras(input: unknown, today: string = helsinkiToday()): FundraisingExtras {
  const data: Record<string, unknown> = input && typeof input === 'object' && !Array.isArray(input) ? input as Record<string, unknown> : {};
  const opens = isoDate(data.start_date) ?? isoDate(data.planned_start_date);
  return { bic: text(data.bic), area: text(data.area), opens_date: opens, pre_launch: Boolean(opens && today < opens) };
}

const icsText = (value: string) => value.replace(/\\/g, '\\\\').replace(/;/g, '\;').replace(/,/g, '\\,').replace(/\n/g, '\\n');

/** An all-day reminder for the opening day. It holds no personal data. */
export function fundraisingIcs(opensDate: string, pageUrl: string): string {
  const compact = opensDate.replace(/-/g, '');
  const [year, month, day] = opensDate.split('-').map(Number);
  const next = new Date(Date.UTC(year, month - 1, day + 1)).toISOString().slice(0, 10).replace(/-/g, '');
  return [
    'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Mielenosoitukset.fi//Pienkerays//FI', 'CALSCALE:GREGORIAN',
    'BEGIN:VEVENT',
    `UID:pienkerays-${compact}@mielenosoitukset.fi`,
    `DTSTAMP:${compact}T000000Z`,
    `DTSTART;VALUE=DATE:${compact}`,
    `DTEND;VALUE=DATE:${next}`,
    `SUMMARY:${icsText('Pienkeräys aukeaa')}`,
    `DESCRIPTION:${icsText('Mielenosoitukset.fi:n pienkeräys alkaa. Tiedot: ' + pageUrl)}`,
    `URL:${pageUrl}`,
    'END:VEVENT', 'END:VCALENDAR', '',
  ].join('\r\n');
}

/** The configuration without account and payment fields, for pages served before opening. */
export function withoutAccount(data: Record<string, unknown>): Record<string, unknown> {
  const copy = { ...data };
  for (const key of ['iban', 'bic', 'recipient', 'reference', 'payment_url', 'mobilepay_links']) delete copy[key];
  return copy;
}
