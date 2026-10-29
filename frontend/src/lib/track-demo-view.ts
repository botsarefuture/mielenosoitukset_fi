/** Preserve the existing same-origin demonstration analytics beacon protocol. */
export function trackDemoView(endpoint: string, id: string): void {
  if (!/^[a-f\d]{24}$/i.test(id)) return;
  try {
    const url = new URL(endpoint, window.location.origin);
    if (url.origin !== window.location.origin) return;
    const payload = JSON.stringify({ demo_id: id });
    if (typeof navigator.sendBeacon === 'function') {
      try {
        if (navigator.sendBeacon(url.href, new Blob([payload], { type: 'application/json' }))) return;
      } catch { /* Use the existing fetch fallback when beacon delivery is unavailable. */ }
    }
    void fetch(url.href, { method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' }, body: payload, keepalive: true }).catch(() => {});
  } catch { /* Analytics must never interfere with the displayed event. */ }
}
