import { useCallback, useMemo, useState, useSyncExternalStore } from 'react';
import { API_BASE } from '../../../api/base';
import usePollingInterval from '../../../shared/hooks/usePollingInterval';
import useWatchlist from './useWatchlist';
import { getWatchlistStatus, subscribeWatchlistStore } from './watchlistStore';
import { livePriceStatus } from '../model/livePriceStatus.js';

// Single frontend source for the Home watchlist live-price poll. Both Home
// consumers — ActionCenter's trigger digest and WatchlistZone's rows — read the
// same ticker set and hit the same `/live-prices/` endpoint, so a poller in each
// doubled the request every 60s. Mount this ONCE at the Home owner (HomeView) and
// thread `prices`/`priceErr` down as props — mirrors the single-owner useLiveRisk
// pattern, never a fetch per consumer.
//
// `prices` is a { ticker: last } map; `priceErr` flips true on a failed poll so a
// row can render its own quote as stale (ActionCenter simply keeps the last map).
//
// `priceStatus` is the same poll expressed as a load state, for surfaces that
// must not confuse "no name is near its trigger" with "no name has been priced
// yet" (council review 2026-09-07, finding 9). It folds in the WATCHLIST's own
// load state, because an unloaded watchlist yields an empty ticker set that
// looks identical to a genuinely empty one:
//   'loading' — the watchlist or the first quote poll is still in flight
//   'idle'    — watchlist loaded and empty: there is nothing to price, ANSWERED
//   'ready'   — quotes landed
//   'error'   — the watchlist or the quote poll failed
export default function useLivePrices() {
  const { watchlist } = useWatchlist();
  const watchlistStatus = useSyncExternalStore(subscribeWatchlistStore, getWatchlistStatus);
  const [prices, setPrices] = useState({});
  const [priceErr, setPriceErr] = useState(false);
  const [fetchStatus, setFetchStatus] = useState('loading');

  const tickers = useMemo(() => [...watchlist].sort(), [watchlist]);
  const tickersKey = tickers.join(',');

  const fetchPrices = useCallback(() => {
    if (!tickersKey) return;
    // fetch does not reject on 4xx/5xx — guard response.ok before json().
    fetch(`${API_BASE}/live-prices/?tickers=${encodeURIComponent(tickersKey)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('prices'))))
      .then((d) => { setPrices(d || {}); setPriceErr(false); setFetchStatus('ready'); })
      .catch(() => { setPriceErr(true); setFetchStatus('error'); });
  }, [tickersKey]);

  // Visibility-gated poll (pauses on a hidden tab); cadence unchanged at 60s.
  usePollingInterval(fetchPrices, 60000);

  const priceStatus = livePriceStatus(watchlistStatus, tickersKey, fetchStatus);

  return { prices, priceErr, priceStatus };
}
