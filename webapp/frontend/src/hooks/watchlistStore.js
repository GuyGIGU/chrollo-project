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
  // Load state so an empty records list is never ambiguous: 'idle' (never
  // asked) / 'loading' (first ask in flight) / 'ready' (a GET landed — an
  // empty list is CONFIRMED empty) / 'error' (failed with nothing to show).
  // A surface that renders "your watchlist is empty" must key on 'ready'.
  status: 'idle',
  inflight: null,
  listeners: new Set(),
};

// Bumped by every toggle; a GET response issued before the bump is stale and
// must not clobber the optimistic state (review finding 2026-08-12).
let mutationEpoch = 0;

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

export function getWatchlistActiveSet() {
  return store.activeSet;
}

// The dated records themselves (active saves, newest write first) for surfaces
// that render MORE than membership — the Home watchlist table reads save_date
// for its saved-age column. Same stable-reference discipline as activeSet.
export function getWatchlistRecords() {
  return store.records;
}

export function getWatchlistStatus() {
  return store.status;
}

function setStatus(status) {
  if (store.status === status) return;
  store.status = status;
  emit();
}

export function fetchWatchlist() {
  if (store.inflight) return store.inflight;
  const epochAtIssue = mutationEpoch;
  if (store.status !== 'ready') setStatus('loading');
  const request = fetch(`${API_BASE}/watchlist/`)
    .then((response) => {
      if (!response.ok) throw new Error(`watchlist ${response.status}`);
      return response.json();
    })
    .then((items) => {
      // A toggle happened while this GET was in flight: its read-time
      // snapshot predates the write — drop it, the toggle path reconciles.
      if (epochAtIssue === mutationEpoch) setRecords(items);
      setStatus('ready');
    })
    .catch((error) => {
      console.error('Watchlist load failed', error);
      // A failed refresh keeps showing what we have; 'error' only with
      // nothing to show (the screenerStore rule).
      setStatus(store.records.length ? 'ready' : 'error');
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
  mutationEpoch += 1;
  const wasOn = store.activeSet.has(ticker);
  if (wasOn) {
    const removed = store.records.find((r) => r.ticker === ticker);
    setRecords(store.records.filter((r) => r.ticker !== ticker));
    return fetch(`${API_BASE}/watchlist/${encodeURIComponent(ticker)}`, {
      method: 'DELETE',
      headers: CLIENT_HEADER,
    })
      .then((response) => {
        // 404 = the server already agrees the star is off — success, never
        // a rollback (a rollback here wedges the star un-removable).
        if (response.status === 404) return;
        if (!response.ok) throw new Error(`watchlist delete ${response.status}`);
        // Reconcile from our own outcome, never assume the optimistic
        // removal survived intermediate writes.
        setRecords(store.records.filter((r) => r.ticker !== ticker));
      })
      .catch((error) => {
        console.error('Watchlist toggle failed, reverting', error);
        if (!store.activeSet.has(ticker) && removed) {
          setRecords([removed, ...store.records]);
        }
      });
  }

  const optimistic = {
    // No id until the server answers — the row's shape must still match a real
    // one, so surfaces keying off `id` see "not yet" instead of undefined.
    id: null, ticker, created_at: null, save_date: null, pinned: false, pin_scan_date: null,
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
      // Upsert: replace the optimistic row, or prepend if it was clobbered.
      const rest = store.records.filter((r) => r.ticker !== ticker);
      setRecords([item, ...rest]);
    })
    .catch((error) => {
      console.error('Watchlist toggle failed, reverting', error);
      setRecords(store.records.filter(
        (r) => !(r.ticker === ticker && r.save_date == null)));
    });
}
