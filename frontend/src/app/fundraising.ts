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
