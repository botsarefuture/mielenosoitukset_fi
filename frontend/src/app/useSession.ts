import { useCallback, useEffect, useRef, useState } from 'react';
import { mergeBridgeSession, readBridge } from './bridge';
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
    if (!initial.authBridge && !initial.unverified) return;
    const url = new URL(options.endpoint, window.location.origin);
    for (const [key, value] of Object.entries(JSON.parse(scopeKey) as Record<string, string>)) url.searchParams.set(key, value);
    setStatus('loading');
    const result = await readBridge(url.pathname + url.search, { normalize: normalizeSession, signal });
    if (!active.current || result.kind === 'aborted') return;
    if (result.kind === 'ready') { setSession(mergeBridgeSession(initial, result.session)); setStatus('ready'); }
    else setStatus('unavailable');
  }, [initial, options.endpoint, scopeKey]);

  useEffect(() => {
    if (options.refreshOnMount === false || (!initial.authBridge && !initial.unverified)) return;
    const controller = new AbortController();
    void refresh(controller.signal);
    return () => controller.abort();
  }, [initial.authBridge, initial.unverified, options.refreshOnMount, refresh]);

  return { session, status, refresh: () => refresh() };
}
