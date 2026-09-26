// The glance's fetch discipline, for the two resolvers that must leave the page
// (a pinned watchlist save's stored snapshot, an archive row's bounded window).
//
// Hovering is a SWEEP: an operator dragging down a 24-row table would otherwise
// fire 24 requests, and the archive path reaches a vendor whose rate bucket the
// nightly scans depend on. So: nothing is requested before the intent gate has
// passed (the caller's job), each key is fetched at most once per session, a
// repeat hover is free, and identical in-flight keys share one promise.
//
// Bounded on purpose — an unbounded map of 45-77KB replay envelopes is a leak
// with a friendly name. Oldest-first eviction (Map preserves insertion order),
// and a re-read refreshes recency so the name being swept stays resident.

const MAX_ENTRIES = 24;

export function createGlanceCache(limit = MAX_ENTRIES) {
  const entries = new Map();  // key -> resolved value
  const inflight = new Map(); // key -> promise

  return {
    get(key) {
      if (!entries.has(key)) return undefined;
      const value = entries.get(key);
      entries.delete(key);
      entries.set(key, value); // touch: most recently used goes last
      return value;
    },

    has: (key) => entries.has(key),

    set(key, value) {
      if (entries.has(key)) entries.delete(key);
      entries.set(key, value);
      while (entries.size > limit) {
        // Evict one at a time from the oldest end — never clear() the whole
        // map, which would throw away the sweep the operator is mid-way through.
        const oldest = entries.keys().next();
        if (oldest.done) break;
        entries.delete(oldest.value);
      }
    },

    // Fetch once per key. Concurrent callers share the in-flight promise; a
    // rejection is NOT cached, so a later hover may legitimately retry.
    load(key, loader) {
      if (entries.has(key)) return Promise.resolve(this.get(key));
      const pending = inflight.get(key);
      if (pending) return pending;
      const promise = Promise.resolve()
        .then(loader)
        .then((value) => {
          this.set(key, value);
          return value;
        })
        .finally(() => {
          if (inflight.get(key) === promise) inflight.delete(key);
        });
      inflight.set(key, promise);
      return promise;
    },

    size: () => entries.size,
    clear() { entries.clear(); inflight.clear(); },
  };
}
