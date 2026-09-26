// The Watchlist page's candle cache, on the watchlistStore/screenerStore
// precedent: a module-level store + listeners Set + emit, consumed through
// useSyncExternalStore. Responses land in a cache KEYED BY TICKER, so the
// displayed chart is always the derivation "cache entry for the currently
// selected ticker" — rapid rail-clicking is safe with zero cancellation or
// epoch logic, because a late response lands in its own key and can never
// clobber the pane now showing a different ticker (latest-wins by
// construction). Each entry carries ONE status value, never separate
// loading/error booleans.
//
// Freshness contract (council review 2026-08-17, findings 3+4):
// - Envelope entries SERVE-STALE-THEN-REVALIDATE: a ready entry keeps
//   rendering while every call issues a background refetch, so an always-on
//   tab picks up tonight's scan rewrite on the next selection instead of
//   serving yesterday's candles forever. An arrival identical to the cached
//   generation keeps the OLD object reference, so the pane memo (and three
//   charts) never rebuild on a no-change revalidate.
// - Each entry records the universe key it was fetched with (EC-37): a pin
//   change makes the cached entry a mismatch and the revalidate replaces it.
// - Batch cells: error cells are re-askable through revalidateBatchCandles
//   (route mount / selecting the errored name); fetchBatchCandles itself
//   only asks for cell-less names, and every asked-for name ABSENT from the
//   response is stamped with a terminal error cell in the same merge — "the
//   server declined to answer" is a recorded outcome, never an invitation
//   to refetch (the infinite-loop finding).
// Explicit .js so bare node (the node --test store suite) can resolve this
// module; Vite resolves it identically.
import { API_BASE } from '../../../api/base.js';

const CLIENT_HEADER = { 'X-Chrollo-Client': 'chrollo-dashboard' };

const store = {
  byTicker: {},   // ticker -> { status: 'loading'|'ready'|'error', universeKey, envelope? }
  batch: {},      // ticker -> { status, candles, volumes } (card-grid cells)
  inflight: {},   // ticker -> in-flight envelope promise (dedup)
  batchInflight: new Set(), // tickers inside a running batch
  listeners: new Set(),
};

const emit = () => {
  for (const listener of store.listeners) listener();
};

export const subscribeCandlesStore = (listener) => {
  store.listeners.add(listener);
  return () => store.listeners.delete(listener);
};

// Whole-map getters with stable references (replaced immutably on change) so
// useSyncExternalStore consumers can select their slice during render.
export const getCandleEnvelopes = () => store.byTicker;
export const getBatchCells = () => store.batch;

const setEntry = (ticker, entry) => {
  store.byTicker = { ...store.byTicker, [ticker]: entry };
  emit();
};

// Cheap same-generation test for a revalidate arrival: the cache meta stamp,
// the ticker's own last session, and the verdict. When all agree, the panel
// has not moved and the cached object keeps its identity.
const sameEnvelopeGeneration = (prev, envelope) => (
  prev?.status === 'ready'
  && prev.envelope?.cache_last_modified === envelope.cache_last_modified
  && prev.envelope?.last_bar_date === envelope.last_bar_date
  && prev.envelope?.status === envelope.status
);

// The selected-ticker envelope: all three timeframes in one request. The pin
// universe key (EC-37) travels when the watchlist record carries one. Always
// safe to call — in-flight dedup'd, and a ready entry keeps serving while
// the request lands (stale-while-revalidate).
export function fetchTickerCandles(ticker, universeKey = null) {
  if (!ticker) return Promise.resolve();
  if (store.inflight[ticker]) return store.inflight[ticker];
  const pin = universeKey || null;
  const existing = store.byTicker[ticker];
  if (!existing || existing.status !== 'ready') {
    setEntry(ticker, { status: 'loading', universeKey: pin });
  }
  const query = pin ? `?universe=${encodeURIComponent(pin)}` : '';
  const request = fetch(
    `${API_BASE}/candles/${encodeURIComponent(ticker)}${query}`,
    { headers: CLIENT_HEADER })
    .then((response) => {
      if (!response.ok) throw new Error(`candles ${response.status}`);
      return response.json();
    })
    .then((envelope) => {
      const prev = store.byTicker[ticker];
      if (prev && prev.universeKey === pin && sameEnvelopeGeneration(prev, envelope)) {
        return; // identical generation — keep the reference, rebuild nothing
      }
      setEntry(ticker, { status: 'ready', universeKey: pin, envelope });
    })
    .catch((error) => {
      console.error(`Candles load failed for ${ticker}`, error);
      // A failed REVALIDATE keeps serving the cached envelope (the next
      // selection retries); only a fetch with nothing cached shows error.
      if (store.byTicker[ticker]?.status !== 'ready') {
        setEntry(ticker, { status: 'error', universeKey: pin });
      }
    })
    .finally(() => {
      delete store.inflight[ticker];
    });
  store.inflight[ticker] = request;
  return request;
}

const pinsParam = (tickers, pins) => {
  const pairs = tickers
    .filter((t) => pins && pins[t])
    .map((t) => `${t}:${pins[t]}`);
  return pairs.length ? `&pins=${encodeURIComponent(pairs.join(','))}` : '';
};

// Same-generation test for a batch cell: verdict + window length + final
// bar's time and close. When all agree the cell keeps its identity, so a
// mount revalidate that changes nothing rebuilds zero card charts.
const sameCellGeneration = (prev, cell) => {
  if (!prev || prev.status !== cell.status) return false;
  const a = prev.candles || [];
  const b = cell.candles || [];
  if (a.length !== b.length) return false;
  if (!a.length) return true;
  const last = a.length - 1;
  return a[last].time === b[last].time && a[last].close === b[last].close;
};

function requestBatch(wanted, pins) {
  for (const t of wanted) store.batchInflight.add(t);
  return fetch(
    `${API_BASE}/candles/?tickers=${encodeURIComponent(wanted.join(','))}${pinsParam(wanted, pins)}`,
    { headers: CLIENT_HEADER })
    .then((response) => {
      if (!response.ok) throw new Error(`batch candles ${response.status}`);
      return response.json();
    })
    .then((data) => {
      const arrived = (data && data.tickers) || {};
      const merged = { ...store.batch };
      for (const t of wanted) {
        // A name the server declined to echo (grammar-dropped legacy row)
        // gets a TERMINAL error cell — a recorded outcome that renders,
        // never a hole that re-joins the fetch plan forever.
        const cell = arrived[t] || { status: 'error', candles: [], volumes: [] };
        merged[t] = sameCellGeneration(store.batch[t], cell) ? store.batch[t] : cell;
      }
      store.batch = merged;
      emit();
    })
    .catch((error) => {
      console.error('Batch candles load failed', error);
      const failed = {};
      for (const t of wanted) {
        // Never downgrade a good cached cell over a failed revalidate.
        if (store.batch[t]?.status === 'ok') continue;
        failed[t] = { status: 'error', candles: [], volumes: [] };
      }
      store.batch = { ...store.batch, ...failed };
      emit();
    })
    .finally(() => {
      for (const t of wanted) store.batchInflight.delete(t);
    });
}

// ONE batched request for the card grid's off-scan tickers — only names with
// no cell at all (the card plan's toFetch); errored cells are NOT re-asked
// here (that is revalidateBatchCandles' job), so plan→fetch can never loop.
export function fetchBatchCandles(tickers, pins = null) {
  const wanted = (tickers || []).filter(
    (t) => t && !store.batch[t] && !store.batchInflight.has(t));
  if (!wanted.length) return Promise.resolve();
  return requestBatch(wanted, pins);
}

// Re-ask EVERY named cell (serving stale meanwhile): the route-mount
// freshness pass, and the retry path for errored cells. Identical arrivals
// keep their references, so an unchanged panel rebuilds nothing.
export function revalidateBatchCandles(tickers, pins = null) {
  const wanted = (tickers || []).filter(
    (t) => t && !store.batchInflight.has(t));
  if (!wanted.length) return Promise.resolve();
  return requestBatch(wanted, pins);
}
