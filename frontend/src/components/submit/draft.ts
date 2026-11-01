/**
 * Browser draft storage for the submission form.
 *
 * Ported from `static/js/submit-draft.js` so an in-progress draft written by
 * the legacy page restores in the React page and vice versa. The on-disk
 * format (key, version, field names, limits, TTL) is unchanged on purpose.
 */
import type { Organizer, SubmitFields } from './types';

export const DRAFT_KEY = 'mielenosoitukset.submit-draft.v2';
export const DRAFT_VERSION = 2;
const DRAFT_TTL_MS = 24 * 60 * 60 * 1000;
const MAX_DRAFT_BYTES = 150000;
const MAX_ORGANIZERS = 20;
const MAX_DESCRIPTION_CHARACTERS = 50000;

/** Submitted field names, matching the legacy draft payload. */
const FIELD_NAMES = [
  'facebook',
  'facebook_imported',
  'facebook_image_url',
  'title',
  'tags',
  'default_language',
  'date',
  'start_time',
  'end_time',
  'type',
  'route',
  'city',
  'address',
  'submitter_role',
  'submitter_name',
  'submitter_email',
] as const;

type FieldName = (typeof FIELD_NAMES)[number];

const ALLOWED_DELTA_ATTRIBUTES = new Set(['bold', 'italic', 'link', 'blockquote', 'list']);

export type DraftOperation = {
  insert: string;
  attributes?: Record<string, true>;
};

export type DraftDelta = { ops: DraftOperation[] };

export type StoredOrganizer = {
  name: string;
  email: string;
  website: string;
  isPrivate: boolean;
  showName: boolean;
  showEmail: boolean;
};

export type StoredDraft = {
  version: number;
  savedAt: number;
  step: number;
  fields: Partial<Record<FieldName, string>>;
  organizers: StoredOrganizer[];
  descriptionDelta: DraftDelta | null;
};

/** Minimal storage surface so tests can inject a fake. */
export type DraftStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem' | 'key' | 'length'>;

function storageOf(candidate?: DraftStorage | null): DraftStorage | null {
  if (candidate) return candidate;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function storageKeys(storage: DraftStorage): string[] {
  const keys: string[] = [];
  try {
    for (let index = 0; index < storage.length; index += 1) {
      const key = storage.key(index);
      if (key) keys.push(key);
    }
  } catch {
    return [];
  }
  return keys;
}

function legacyKeys(storage: DraftStorage): string[] {
  // Deep links from the old wizard must not survive a downgrade.
  return storageKeys(storage).filter((key) => key === 'form_step' || key.startsWith('form_'));
}

function clampStep(value: unknown): number {
  const step = typeof value === 'number' ? value : Number.parseInt(String(value ?? ''), 10);
  return Number.isInteger(step) && step >= 1 && step <= 5 ? step : 1;
}

function boundedString(value: unknown, maxLength = 20000): string {
  return typeof value === 'string' ? value.slice(0, maxLength) : '';
}

/** Keep text-only operations with supported formatting, or reject the delta. */
export function normalizeDelta(raw: unknown): DraftDelta | null {
  const candidate = raw as { ops?: unknown } | null;
  if (!candidate || !Array.isArray(candidate.ops) || candidate.ops.length > 2000) return null;

  let characterCount = 0;
  const ops: DraftOperation[] = [];
  for (const rawOperation of candidate.ops as Array<Record<string, unknown>>) {
    if (!rawOperation || typeof rawOperation.insert !== 'string') return null;
    characterCount += rawOperation.insert.length;
    if (characterCount > MAX_DESCRIPTION_CHARACTERS) return null;

    const operation: DraftOperation = { insert: rawOperation.insert };
    const rawAttributes = rawOperation.attributes;
    if (rawAttributes && typeof rawAttributes === 'object') {
      const attributes: Record<string, true> = {};
      Object.keys(rawAttributes as Record<string, unknown>).forEach((name) => {
        if (ALLOWED_DELTA_ATTRIBUTES.has(name)) attributes[name] = true;
      });
      if (Object.keys(attributes).length) operation.attributes = attributes;
    }
    ops.push(operation);
  }
  return { ops };
}

function normalizeOrganizer(raw: unknown): StoredOrganizer | null {
  if (!raw || typeof raw !== 'object') return null;
  const row = raw as Record<string, unknown>;
  return {
    name: boundedString(row.name, 200),
    email: boundedString(row.email, 254),
    website: boundedString(row.website, 2048),
    isPrivate: row.isPrivate === true,
    showName: row.showName !== false,
    showEmail: row.showEmail !== false,
  };
}

/** Reject invalid versions/timestamps and normalize the restorable payload. */
export function normalizeDraft(raw: unknown): StoredDraft | null {
  if (!raw || typeof raw !== 'object') return null;
  const candidate = raw as Record<string, unknown>;
  if (candidate.version !== DRAFT_VERSION || typeof candidate.savedAt !== 'number') return null;
  if (Date.now() - candidate.savedAt > DRAFT_TTL_MS || candidate.savedAt > Date.now() + 60000) {
    return null;
  }

  const fields: Partial<Record<FieldName, string>> = {};
  const rawFields = candidate.fields;
  if (rawFields && typeof rawFields === 'object') {
    FIELD_NAMES.forEach((name) => {
      const value = (rawFields as Record<string, unknown>)[name];
      if (typeof value === 'string') fields[name] = boundedString(value);
    });
  }

  const organizers = Array.isArray(candidate.organizers)
    ? candidate.organizers.slice(0, MAX_ORGANIZERS).map(normalizeOrganizer).filter((row): row is StoredOrganizer => Boolean(row))
    : [];

  return {
    version: DRAFT_VERSION,
    savedAt: candidate.savedAt,
    step: clampStep(candidate.step),
    fields,
    organizers,
    descriptionDelta: normalizeDelta(candidate.descriptionDelta),
  };
}

/** Read a validated draft, dropping oversized, malformed or expired entries. */
export function readDraft(storage?: DraftStorage | null): StoredDraft | null {
  const target = storageOf(storage);
  if (!target) return null;
  let serialized: string | null = null;
  try {
    serialized = target.getItem(DRAFT_KEY);
  } catch {
    return null;
  }
  if (!serialized) return null;
  if (serialized.length > MAX_DRAFT_BYTES) {
    try {
      target.removeItem(DRAFT_KEY);
    } catch {
      /* storage unavailable */
    }
    return null;
  }
  try {
    const draft = normalizeDraft(JSON.parse(serialized));
    if (!draft) target.removeItem(DRAFT_KEY);
    return draft;
  } catch {
    try {
      target.removeItem(DRAFT_KEY);
    } catch {
      /* storage unavailable */
    }
    return null;
  }
}

/** Migrate the previous per-field storage keys, then remove them. */
export function readLegacyDraft(storage?: DraftStorage | null): StoredDraft | null {
  const target = storageOf(storage);
  if (!target) return null;
  const get = (key: string) => {
    try {
      return target.getItem(key);
    } catch {
      return null;
    }
  };

  const fields: Partial<Record<FieldName, string>> = {};
  FIELD_NAMES.forEach((name) => {
    const value = get(`form_${name}`);
    if (value !== null) fields[name] = boundedString(value);
  });

  const organizers: StoredOrganizer[] = [];
  for (let index = 1; index <= MAX_ORGANIZERS; index += 1) {
    const name = get(`form_organizer_name_${index}`);
    const email = get(`form_organizer_email_${index}`);
    const website = get(`form_organizer_website_${index}`);
    if (name === null && email === null && website === null) continue;
    organizers.push({
      name: boundedString(name, 200),
      email: boundedString(email, 254),
      website: boundedString(website, 2048),
      isPrivate: false,
      showName: true,
      showEmail: true,
    });
  }

  const hasContent = Object.values(fields).some(Boolean) || organizers.length > 0;
  const draft: StoredDraft | null = hasContent
    ? {
        version: DRAFT_VERSION,
        savedAt: Date.now(),
        step: clampStep(get('form_step')),
        fields,
        organizers,
        descriptionDelta: null,
      }
    : null;

  legacyKeys(target).forEach((key) => {
    try {
      target.removeItem(key);
    } catch {
      /* storage unavailable */
    }
  });
  if (draft) writeDraft(draft, target);
  return draft;
}

/** Persist a draft when it fits the byte budget. */
export function writeDraft(draft: StoredDraft, storage?: DraftStorage | null): boolean {
  const target = storageOf(storage);
  if (!target) return false;
  const serialized = JSON.stringify(draft);
  if (serialized.length > MAX_DRAFT_BYTES) return false;
  try {
    target.setItem(DRAFT_KEY, serialized);
    return true;
  } catch {
    return false;
  }
}

/** Remove the current draft and any legacy fragment. */
export function clearDraft(storage?: DraftStorage | null): void {
  const target = storageOf(storage);
  if (!target) return;
  try {
    target.removeItem(DRAFT_KEY);
  } catch {
    /* storage unavailable */
  }
  legacyKeys(target).forEach((key) => {
    try {
      target.removeItem(key);
    } catch {
      /* storage unavailable */
    }
  });
}

/** Map form state onto the legacy draft field names. */
export function fieldsToDraftFields(fields: SubmitFields): Record<FieldName, string> {
  return {
    facebook: fields.facebook,
    facebook_imported: fields.facebookImported ? '1' : '',
    facebook_image_url: fields.facebookImageUrl,
    title: fields.title,
    tags: fields.tags,
    default_language: fields.defaultLanguage,
    date: fields.date,
    start_time: fields.startTime,
    end_time: fields.endTime,
    type: fields.eventType,
    route: fields.route,
    city: fields.city,
    address: fields.address,
    submitter_role: fields.submitterRole,
    submitter_name: fields.submitterName,
    submitter_email: fields.submitterEmail,
  };
}

/** Merge restored draft fields over the server defaults. */
export function applyDraftFields(fields: SubmitFields, restored: StoredDraft['fields']): SubmitFields {
  const read = (name: FieldName, fallback: string) => {
    const value = restored[name];
    return typeof value === 'string' ? value : fallback;
  };
  return {
    ...fields,
    facebook: read('facebook', fields.facebook),
    facebookImported: read('facebook_imported', '') === '1',
    facebookImageUrl: read('facebook_image_url', fields.facebookImageUrl),
    title: read('title', fields.title),
    tags: read('tags', fields.tags),
    defaultLanguage: read('default_language', fields.defaultLanguage),
    date: read('date', fields.date),
    startTime: read('start_time', fields.startTime),
    endTime: read('end_time', fields.endTime),
    eventType: read('type', fields.eventType),
    route: read('route', fields.route),
    city: read('city', fields.city),
    address: read('address', fields.address),
    submitterRole: read('submitter_role', fields.submitterRole),
    submitterName: read('submitter_name', fields.submitterName),
    submitterEmail: read('submitter_email', fields.submitterEmail),
  };
}

export function draftOrganizers(organizers: StoredOrganizer[]): Organizer[] {
  return organizers.slice(0, MAX_ORGANIZERS).map((row, index) => ({ key: `restored-${index}`, ...row }));
}

/**
 * Whether the draft is worth storing at all.
 *
 * `default_language` always holds the server default, so counting it made an
 * untouched form look like a draft: every visit re-saved a blank entry and the
 * "draft restored" notice appeared even after the user deleted the draft.
 */
export function draftHasContent(draft: StoredDraft): boolean {
  const fieldContent = Object.entries(draft.fields).some(
    ([name, value]) => name !== 'default_language' && Boolean(value),
  );
  const organizerContent = draft.organizers.some(
    (organizer) =>
      organizer.name ||
      organizer.email ||
      organizer.website ||
      organizer.isPrivate ||
      !organizer.showName ||
      !organizer.showEmail,
  );
  const descriptionContent = draft.descriptionDelta?.ops.some((operation) => operation.insert.trim() !== '');
  return Boolean(fieldContent || organizerContent || descriptionContent || draft.step > 1);
}

export { MAX_ORGANIZERS };
