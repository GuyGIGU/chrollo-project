// The watchlist ledger's ONE client-side copy (Finviz plan Task 8), on the
// screenerStore precedent: a module-level object + listeners Set + emit,
// consumed through useSyncExternalStore. It holds exactly one thing — the
// dated records list from GET /watchlist/ — and the ACTIVE ticker Set is
// derived from it (memoized per change so snapshot getters return stable
// references; never maintained as parallel state). A star toggled on the
// Screener is instantly visible on Home because every mount shares this store.
import { API_BASE } from '../api';

const CLIENT_HEADER = { 'X-Chrollo-Client': 'chrollo-dashboard' };

const store = {
  records: [],          // [{ticker, created_at, save_date, pinned, pin_scan_date}]
  activeSet: new Set(), // derived from records at every write — one truth
  failed: false,
  inflight: null,
  listeners: new Set(),
};

function emit() {
  for (const listener of store.listeners) listener();
}

function setRecords(records) {
  store.records = records;
  store.activeSet = new Set(records.map((r) => r.ticker));
  emit();
}

export function subscribeWatchlistStore(listener) {
  store.listeners.add(listener);
  return () => store.listeners.delete(listener);
}

export function getWatchlistRecords() {
  return store.records;
}

export function getWatchlistActiveSet() {
  return store.activeSet;
}

export function fetchWatchlist({ fresh = false } = {}) {
  if (store.inflight) {
    // A dedup'd in-flight response can predate a write; `fresh` awaits it and
    // then re-fetches (the screenerStore fresh semantic).
    if (!fresh) return store.inflight;
    return store.inflight.catch(() => {}).then(() => fetchWatchlist());
  }
  const request = fetch(`${API_BASE}/watchlist/`)
    .then((response) => {
      if (!response.ok) throw new Error(`watchlist ${response.status}`);
      return response.json();
    })
    .then((items) => {
      store.failed = false;
      setRecords(items);
    })
    .catch((error) => {
      store.failed = true;
      console.error('Watchlist load failed', error);
      emit();
    })
    .finally(() => {
      if (store.inflight === request) store.inflight = null;
    });
  store.inflight = request;
  return request;
}

// Optimistic toggle + rollback (the old hook's semantics, now store-wide).
// `saveContext` = { universe, scanDate } — the DISPLAYED scan identity the
// card was rendered from, threaded so the server can refuse to pin a stale
// page (EC-26: the server still resolves pin + snapshot from its own
// artifact; this is what-the-operator-clicked, never chart content).
export function toggleWatchlist(ticker, saveContext = null) {
  const wasOn = store.activeSet.has(ticker);
  if (wasOn) {
    const removed = store.records.find((r) => r.ticker === ticker);
    setRecords(store.records.filter((r) => r.ticker !== ticker));
    return fetch(`${API_BASE}/watchlist/${encodeURIComponent(ticker)}`, {
      method: 'DELETE',
      headers: CLIENT_HEADER,
    })
      .then((response) => {
        if (!response.ok) throw new Error(`watchlist delete ${response.status}`);
      })
      .catch((error) => {
        console.error('Watchlist toggle failed, reverting', error);
        if (!store.activeSet.has(ticker) && removed) {
          setRecords([removed, ...store.records]);
        }
      });
  }

  const optimistic = {
    ticker, created_at: null, save_date: null, pinned: false, pin_scan_date: null,
  };
  setRecords([optimistic, ...store.records]);
  const hasContext = Boolean(saveContext && saveContext.universe);
  return fetch(`${API_BASE}/watchlist/${encodeURIComponent(ticker)}`, {
    method: 'POST',
    headers: hasContext
      ? { ...CLIENT_HEADER, 'Content-Type': 'application/json' }
      : CLIENT_HEADER,
    body: hasContext
      ? JSON.stringify({
          universe: saveContext.universe,
          scan_date: saveContext.scanDate ?? null,
        })
      : undefined,
  })
    .then((response) => {
      if (!response.ok) throw new Error(`watchlist post ${response.status}`);
      return response.json();
    })
    .then((item) => {
      setRecords(store.records.map((r) => (r.ticker === ticker ? item : r)));
    })
    .catch((error) => {
      console.error('Watchlist toggle failed, reverting', error);
      setRecords(store.records.filter(
        (r) => !(r.ticker === ticker && r.save_date == null)));
    });
}
