import type { PublicOrganization } from '../components/organization/types';
import type { ListingBootstrap } from './listing';
import { ttlCache } from './server-cache';

export type OrganizationBootstrap = { profile: PublicOrganization; listing: ListingBootstrap };
export type OrganizationLoad = { status: 'ready'; profile: PublicOrganization }
  | { status: 'not-found' } | { status: 'unavailable' };

const profiles = ttlCache<PublicOrganization>(60_000, 64);
const pending = new Map<string, Promise<OrganizationLoad>>();

/** Public profile data only. Follow, invitation and permission state stays in Flask. */
export async function loadOrganization(readBase: string, id: string): Promise<OrganizationLoad> {
  const key = `${readBase}\n${id}`;
  const cached = profiles.get(key);
  if (cached) return { status: 'ready', profile: cached };
  if (pending.has(key)) return pending.get(key)!;
  if (pending.size >= 16) return { status: 'unavailable' };
  const promise = (async (): Promise<OrganizationLoad> => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 1500);
    try {
      const response = await fetch(`${readBase}/organizations/${encodeURIComponent(id)}`, {
        signal: controller.signal, credentials: 'omit', headers: { Accept: 'application/json' },
      });
      if (response.status === 400 || response.status === 404) return { status: 'not-found' };
      if (!response.ok) return { status: 'unavailable' };
      const data: unknown = await response.json();
      if (!data || typeof data !== 'object' || Array.isArray(data)) return { status: 'unavailable' };
      const raw = data as Record<string, unknown>;
      const fields = ['name', 'description', 'email', 'website', 'logo'] as const;
      if (raw._id !== id || fields.some(field => typeof raw[field] !== 'string')
        || typeof raw.verified !== 'boolean' || !raw.social_media_links
        || typeof raw.social_media_links !== 'object' || Array.isArray(raw.social_media_links)) return { status: 'unavailable' };
      const social = Object.entries(raw.social_media_links).filter((entry): entry is [string, string] => typeof entry[1] === 'string');
      const profile: PublicOrganization = { _id: id, name: raw.name as string, description: raw.description as string,
        email: raw.email as string, website: raw.website as string, logo: raw.logo as string,
        verified: raw.verified, social_media_links: Object.fromEntries(social) };
      if (JSON.stringify(profile).length <= 128 * 1024 && !/no-store/i.test(response.headers.get('Cache-Control') ?? '')) profiles.set(key, profile);
      return { status: 'ready', profile };
    } catch { return { status: 'unavailable' }; }
    finally { clearTimeout(timer); }
  })().finally(() => pending.delete(key));
  pending.set(key, promise);
  return promise;
}
