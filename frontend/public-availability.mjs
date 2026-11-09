// The status is deliberately independent of event/config caches. An explicit
// lockdown answer applies at once. A failed or timed-out read is not a lockdown:
// it keeps the last explicit "available" answer for a short grace period, so a
// Go API restart does not briefly close the site. Without a recent explicit
// answer, for example right after this process starts, the host fails closed.
export const AVAILABILITY_GRACE_MS = 30_000;

export function availabilityReader(apiReadBase, fetcher = fetch, now = Date.now) {
  let expires = 0;
  let available = false;
  let lastOpenAt = 0;
  let pending;
  return async function read() {
    if (now() < expires) return available;
    if (!pending) pending = (async () => {
      let answer;
      try {
        const response = await fetcher(`${apiReadBase}/public-status`, {
          signal: AbortSignal.timeout(1200), headers: { Accept: 'application/json' },
        });
        const data = response.ok ? await response.json() : null;
        if (typeof data?.available === 'boolean') answer = data.available;
      } catch { /* No answer; decided below. */ }
      if (answer === true) lastOpenAt = now();
      // Never let a later failed read reopen a site that was locked.
      if (answer === false) lastOpenAt = 0;
      available = answer ?? (lastOpenAt > 0 && now() - lastOpenAt <= AVAILABILITY_GRACE_MS);
      expires = now() + 1000;
      return available;
    })().finally(() => { pending = null; });
    return pending;
  };
}
