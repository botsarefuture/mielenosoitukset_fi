/**
 * Small bounded TTL cache for server-side public reads.
 *
 * The host renders metadata only, so the same public documents are read again
 * and again by different visitors. Caching them in the process removes a remote
 * round trip from most page responses. Entries are bounded and expire, failures
 * are never stored, and nothing private is ever put here: only public event
 * metadata and the public home batch.
 */

type Entry<V> = { value: V; expiresAt: number };

export type TtlCache<V> = {
  get(key: string): V | null;
  set(key: string, value: V): void;
  /** Test and diagnostics hook. */
  size(): number;
};

export function ttlCache<V>(ttlMs: number, maxEntries: number): TtlCache<V> {
  const entries = new Map<string, Entry<V>>();
  return {
    get(key) {
      const entry = entries.get(key);
      if (!entry) return null;
      if (entry.expiresAt <= Date.now()) {
        entries.delete(key);
        return null;
      }
      // Refresh insertion order so the map stays an LRU queue.
      entries.delete(key);
      entries.set(key, entry);
      return entry.value;
    },
    set(key, value) {
      entries.delete(key);
      entries.set(key, { value, expiresAt: Date.now() + ttlMs });
      while (entries.size > maxEntries) {
        const oldest = entries.keys().next();
        if (oldest.done) break;
        entries.delete(oldest.value);
      }
    },
    size: () => entries.size,
  };
}
