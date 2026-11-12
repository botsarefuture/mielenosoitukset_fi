import { useCallback, useEffect, useRef, useState } from 'react';
import { normalizeSession } from './session';
import type { SessionSummary } from './session';

export type SessionStatus = 'initial' | 'loading' | 'ready' | 'unavailable';

type Options = {
  /** The read-only Go endpoint (`urls.authMe`). Only used when the server reports `authBridge`. */
  endpoint: string;
  /** Extra read-only scopes such as `{ organization_id: '…' }`. */
  scope?: Record<string, string>;
  /** Re-read on mount. Default true. */
  refreshOnMount?: boolean;
};

/** The fields the Go answer is allowed to replace; everything else keeps the server-rendered value. */
export function mergeBridgeSession(initial: SessionSummary, fresh: SessionSummary): SessionSummary {
  return {
    ...initial,
    authenticated: fresh.authenticated, role: fresh.role, name: fresh.name, picture: fresh.picture,
    globalAdmin: fresh.globalAdmin, hasAdminAccess: fresh.hasAdminAccess, unread: fresh.unread,
    organization: fresh.organization,
  };
}

/**
 * Who is signed in, for anonymous and signed-in visitors alike.
 *
 * The server-rendered summary is the starting value. When the server says the
 * auth bridge is on (`authBridge`), the hook asks the Go `/api/auth/me` once and
 * merges the answer. Flask stays the only authority; this hook never sends a
 * credential itself, only the browser's own same-origin cookie. Any failure
 * keeps the starting value: it never turns a signed-in visitor into a guest or
 * the reverse.
 */
export function useSession(initial: SessionSummary, options: Options) {
  const [session, setSession] = useState<SessionSummary>(initial);
  const [status, setStatus] = useState<SessionStatus>('initial');
  const scopeKey = JSON.stringify(options.scope ?? {});
  const active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  useEffect(() => { setSession(initial); }, [initial]);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    if (!initial.authBridge) return;
    const url = new URL(options.endpoint, window.location.origin);
    for (const [key, value] of Object.entries(JSON.parse(scopeKey) as Record<string, string>)) url.searchParams.set(key, value);
    setStatus('loading');
    try {
      const response = await fetch(url.pathname + url.search, { credentials: 'same-origin', cache: 'no-store', signal,
        headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error('unavailable');
      const raw: unknown = await response.json();
      // A body without a boolean `authenticated` is not an answer; never read it as "signed out".
      if (!raw || typeof raw !== 'object' || typeof (raw as { authenticated?: unknown }).authenticated !== 'boolean') throw new Error('invalid');
      if (active.current) { setSession(mergeBridgeSession(initial, normalizeSession(raw))); setStatus('ready'); }
    } catch {
      if (active.current && !signal?.aborted) setStatus('unavailable');
    }
  }, [initial, options.endpoint, scopeKey]);

  useEffect(() => {
    if (options.refreshOnMount === false || !initial.authBridge) return;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    void refresh(controller.signal).finally(() => clearTimeout(timer));
    return () => { controller.abort(); clearTimeout(timer); };
  }, [initial.authBridge, options.refreshOnMount, refresh]);

  return { session, status, refresh: () => refresh() };
}
