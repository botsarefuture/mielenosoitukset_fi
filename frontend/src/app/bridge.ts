// The pure parts of the read-only Go session bridge (kept free of runtime imports so node can test them).
import type { SessionSummary } from './session';

export type BridgeRead = { kind: 'ready'; session: SessionSummary } | { kind: 'unavailable' } | { kind: 'aborted' };

/**
 * One read of the Go `/api/auth/me`, with its own timeout. A hang, a non-200 or a body that is not an
 * answer is `unavailable` (never "signed out"). Only the caller's own abort (unmount) is `aborted`.
 */
export async function readBridge(url: string, options: { normalize: (raw: unknown) => SessionSummary; fetcher?: typeof fetch; timeoutMs?: number; signal?: AbortSignal }): Promise<BridgeRead> {
  const { normalize, fetcher = fetch, timeoutMs = 5000, signal } = options;
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
  const forward = () => controller.abort();
  if (signal?.aborted) forward(); else signal?.addEventListener('abort', forward);
  try {
    const response = await fetcher(url, { credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
      headers: { Accept: 'application/json' } });
    if (!response.ok) return { kind: 'unavailable' };
    const raw: unknown = await response.json();
    // A body without a boolean `authenticated` is not an answer; never read it as "signed out".
    if (!raw || typeof raw !== 'object' || typeof (raw as { authenticated?: unknown }).authenticated !== 'boolean') return { kind: 'unavailable' };
    return { kind: 'ready', session: normalize(raw) };
  } catch {
    return signal?.aborted && !timedOut ? { kind: 'aborted' } : { kind: 'unavailable' };
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', forward);
  }
}

/** The fields the Go answer is allowed to replace; everything else keeps the server-rendered value. */
export function mergeBridgeSession(initial: SessionSummary, fresh: SessionSummary): SessionSummary {
  // Signed-in-only extras must not outlive a sign-out seen by the fresh answer.
  const signedOut = !fresh.authenticated;
  return {
    ...initial,
    ...(signedOut ? { translationJoin: undefined, submission: initial.submission
      ? { ...initial.submission, canEditDemo: false } : undefined } : {}),
    authenticated: fresh.authenticated, role: fresh.role, name: fresh.name, picture: fresh.picture,
    globalAdmin: fresh.globalAdmin, hasAdminAccess: fresh.hasAdminAccess, unread: fresh.unread,
    organization: fresh.organization,
  };
}

