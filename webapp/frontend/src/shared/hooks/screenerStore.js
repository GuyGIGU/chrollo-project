import { API_BASE } from '../../api/base.js';

export const DEFAULT_UNIVERSE = 'us_stocks';

// Module-level shared screener store: ONE cached copy of the (13MB) artifact
// per universe, shared by every consumer (Home's tiles, the grid) and surviving
// route remounts — navigation paints from cache instantly and concurrent
// consumers dedup onto a single in-flight request (each mount still issues one
// background revalidate, as the per-hook cache did). Universe keying preserves
// the old stale-token semantics: a slow fetch that resolves after the user
// switched away updates only its own universe's slot, and status is always
// derived for the universe being asked about. Consumers subscribe via
// useScreenerData (useSyncExternalStore).
const store = {
  byUniverse: {}, // universe -> latest full payload
  failed: {}, // universe -> last fetch errored (only meaningful with no payload)
  inflight: {}, // universe -> in-flight full-fetch promise (dedup)
  earnings: {}, // ticker -> { date, days_until }
  requestedEarnings: new Set(), // negative cache: tickers already asked about
  listeners: new Set(),
};

const emit = () => {
  for (const listener of store.listeners) listener();
};

export const subscribeScreenerStore = (listener) => {
  store.listeners.add(listener);
  return () => store.listeners.delete(listener);
};

export const getScreenerPayload = (universe) => store.byUniverse[universe] || null;

// The whole universe->payload map (replaced immutably on every write, so the
// reference is a stable useSyncExternalStore snapshot). For surfaces that
// look a ticker up across ALL universes — the Watchlist page's overlay lookup.
export const getScreenerPayloads = () => store.byUniverse;

export const getScreenerEarnings = () => store.earnings;

// Map a payload to one explicit status the grid switches on. 'never_scanned'
// (valid universe, no artifact) is distinct from 'empty' (a real scan that
// matched nothing) and from 'loading'/'error'.
const deriveStatus = (payload) => {
  if (payload.status === 'never_scanned') return 'never_scanned';
  return (payload.ordered_tickers || []).length ? 'ready' : 'empty';
};

// Status for a universe: a cached payload always wins (a failed revalidate
// keeps showing the cached scan); 'error' only when a fetch failed with
// nothing to show.
export const getScreenerStatus = (universe) => {
  const payload = store.byUniverse[universe];
  if (payload) return deriveStatus(payload);
  return store.failed[universe] ? 'error' : 'loading';
};

// `fresh: true` guarantees a request issued AFTER this call (a caller that just
// changed the artifact — e.g. the scan runner — must not be served a dedup'd
// response that predates it): an in-flight fetch is awaited, then a new one runs.
export function fetchScreenerUniverse(universe = DEFAULT_UNIVERSE, { fresh = false } = {}) {
  const u = universe || DEFAULT_UNIVERSE;
  if (store.inflight[u]) {
    return fresh
      ? store.inflight[u].then(() => fetchScreenerUniverse(u))
      : store.inflight[u];
  }
  // A retry after a no-data failure shows 'loading' again, not the stale error.
  if (!store.byUniverse[u] && store.failed[u]) {
    store.failed = { ...store.failed, [u]: false };
    emit();
  }
  const run = (async () => {
    try {
      const response = await fetch(`${API_BASE}/screener-data/?universe=${encodeURIComponent(u)}`);
      if (!response.ok) {
        const body = await response.text().catch(() => '');
        console.error(`screener-data ${response.status}: ${body.slice(0, 200)}`);
        store.failed = { ...store.failed, [u]: true };
        return;
      }
      const data = await response.json();
      const cached = store.byUniverse[u];
      const sameGeneration = (cached?.scanned_at || null) === (data.scanned_at || null);
      // A new scan invalidates the earnings negative cache, so visible tickers
      // re-ask (the values stay on screen while they refresh).
      if (!sameGeneration) {
        store.requestedEarnings = new Set();
      }
      // Reference identity is the frontend's rebuild currency (EC-41): a
      // same-generation arrival keeps the OLD payload object so a no-change
      // revalidate rebuilds zero charts.
      if (!cached || !sameGeneration) {
        store.byUniverse = { ...store.byUniverse, [u]: data };
      }
      store.failed = { ...store.failed, [u]: false };
    } catch (error) {
      console.error('Failed to load screener data', error);
      store.failed = { ...store.failed, [u]: true };
    } finally {
      delete store.inflight[u];
      emit();
    }
  })();
  store.inflight[u] = run;
  return run;
}

// Cheap freshness check for pollers (Home's 5-minute tick): pull the slim
// /screener-summary and only re-download the full artifact when a new scan
// actually landed (scanned_at moved). A summary failure keeps the cached data
// and lets the next tick retry.
export async function revalidateScreenerUniverse(universe = DEFAULT_UNIVERSE) {
  const u = universe || DEFAULT_UNIVERSE;
  const cached = store.byUniverse[u];
  if (!cached) return fetchScreenerUniverse(u);
  try {
    const response = await fetch(`${API_BASE}/screener-summary/?universe=${encodeURIComponent(u)}`);
    if (!response.ok) return;
    const summary = await response.json();
    if ((summary.scanned_at || null) !== (cached.scanned_at || null)) {
      await fetchScreenerUniverse(u);
    }
  } catch (error) {
    console.error('screener-summary revalidate failed', error);
  }
}

// Lazy-fetch earnings for the visible page. The negative cache is module-level
// so a Screener remount (navigation) doesn't re-POST for tickers already asked.
export function fetchScreenerEarnings(visibleTickers) {
  const missing = (visibleTickers || []).filter((ticker) => !store.requestedEarnings.has(ticker));
  if (missing.length === 0) return;
  missing.forEach((ticker) => store.requestedEarnings.add(ticker));
  fetch(`${API_BASE}/screener-data/earnings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tickers: missing }),
  })
    .then((response) => {
      if (!response.ok) {
        // A non-ok answer must not stick in the negative cache — re-ask later.
        missing.forEach((ticker) => store.requestedEarnings.delete(ticker));
        return null;
      }
      return response.json();
    })
    .then((data) => {
      if (!data) return;
      store.earnings = { ...store.earnings, ...data };
      emit();
    })
    .catch(() => {
      missing.forEach((ticker) => store.requestedEarnings.delete(ticker));
    });
}
