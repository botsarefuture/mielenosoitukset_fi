import type { ListParams } from './types';

export const FILTERS = ['search', 'city', 'location', 'date_start', 'date_end'] as const;
export const QUERY_FILTERS = [...FILTERS, 'in_past', 'title', 'tag', 'parent_id', 'organization_id', 'include_cancelled', 'max_days_till'];
const positive = (value: string | null, fallback: number) => /^\d+$/.test(value ?? '')
  && Number.isSafeInteger(Number(value)) && Number(value) > 0 ? Number(value) : fallback;

/** Shared by document bootstrap and browser navigation; campaign keys stay out. */
export function listingQuery(search: string, fixed: Record<string, string>): { params: ListParams; page: number } {
  const query = new URLSearchParams(search);
  const params: ListParams = {};
  for (const name of QUERY_FILTERS) {
    const value = query.get(name)?.trim();
    if (value) params[name] = value;
  }
  Object.assign(params, fixed);
  params.per_page = Math.min(positive(query.get('per_page'), 12), 100);
  return { params, page: positive(query.get('page'), 1) };
}
