/** Host actions stay on their own origin; the public Go read API receives no cookies. */
export function accountEndpoint(template: string, id: string): string {
  const url = new URL(template.replaceAll('__EVENT_ID__', encodeURIComponent(id)), window.location.origin);
  if (url.origin !== window.location.origin || !['https:', 'http:'].includes(url.protocol)) throw new Error('Invalid account endpoint');
  return url.href;
}
class AccountError extends Error {}
export async function accountRequest(endpoint: string, options: RequestInit, csrfToken?: string): Promise<Record<string, unknown>> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  options.signal?.addEventListener('abort', abort, { once: true });
  if (options.signal?.aborted) controller.abort();
  const timeout = window.setTimeout(abort, 15_000);
  try {
    const response = await fetch(endpoint, { ...options, signal: controller.signal, credentials: 'same-origin', redirect: 'error',
      headers: { Accept: 'application/json', ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}), ...options.headers } });
    const data: unknown = await response.json();
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Invalid action response');
    const payload = data as Record<string, unknown>;
    if (!response.ok || payload.error || payload.status === 'ERROR') throw new AccountError(typeof payload.message === 'string' ? payload.message : '');
    return payload;
  } finally { window.clearTimeout(timeout); options.signal?.removeEventListener('abort', abort); }
}
export function actionMessage(error: unknown, fallback: string) { return error instanceof AccountError && error.message ? error.message : fallback; }
