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
// Explicit .js so bare node (the node --test store suite) can resolve this
// module; Vite resolves it identically.
import { API_BASE } from '../../../api/base.js';

const CLIENT_HEADER = { 'X-Chrollo-Client': 'chrollo-dashboard' };

const store = {
  byTicker: {},   // ticker -> { status: 'loading'|'ready'|'error', universeKey, envelope? }
  inflight: {},   // ticker -> in-flight envelope promise (dedup)
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
