// The status is deliberately independent of event/config caches. Fail closed;
// an unavailable control plane must not silently undo a security lockdown.
export function availabilityReader(apiReadBase, fetcher = fetch) {
  let expires = 0;
  let available = false;
  let pending;
  return async function read() {
    if (Date.now() < expires) return available;
    if (!pending) pending = (async () => {
      try {
        const response = await fetcher(`${apiReadBase}/public-status`, {
          signal: AbortSignal.timeout(1200), headers: { Accept: 'application/json' },
        });
        const data = response.ok ? await response.json() : null;
        available = data?.available === true;
      } catch { available = false; }
      expires = Date.now() + 1000;
      return available;
    })().finally(() => { pending = null; });
    return pending;
  };
}
