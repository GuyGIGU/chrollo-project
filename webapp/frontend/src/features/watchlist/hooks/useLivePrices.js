import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
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
//
// `extraKey` (comma-joined tickers) prices names off this week's list too: the
// Watchlist page's past week, whose % Diff since add still reads today's quote.
export default function useLivePrices(extraKey = '') {
  const { watchlist } = useWatchlist();
  const watchlistStatus = useSyncExternalStore(subscribeWatchlistStore, getWatchlistStatus);
  const [prices, setPrices] = useState({});
  const [priceErr, setPriceErr] = useState(false);
  const [fetchStatus, setFetchStatus] = useState('loading');
  const requestId = useRef(0);

  const tickers = useMemo(() => [...new Set([...watchlist, ...extraKey.split(',').filter(Boolean)])].sort(),
    [watchlist, extraKey]);
  const tickersKey = tickers.join(',');

  const fetchPrices = useCallback(() => {
    if (!tickersKey) return;
    const id = ++requestId.current;
    // fetch does not reject on 4xx/5xx — guard response.ok before json().
    fetch(`${API_BASE}/live-prices/?tickers=${encodeURIComponent(tickersKey)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('prices'))))
      .then((d) => { if (id === requestId.current) { setPrices(d || {}); setPriceErr(false); setFetchStatus('ready'); } })
      .catch(() => { if (id === requestId.current) { setPriceErr(true); setFetchStatus('error'); } });
  }, [tickersKey]);

  // The list usually arrives after mount: price new membership immediately,
  // instead of waiting up to a minute for the ref-based interval's first tick.
  useEffect(() => {
    if (!document.hidden) fetchPrices();
    return () => { requestId.current += 1; };
  }, [fetchPrices]);
  // Visibility-gated poll (pauses on a hidden tab); cadence unchanged at 60s.
  usePollingInterval(fetchPrices, 60000, { immediate: false });

  const priceStatus = livePriceStatus(watchlistStatus, tickersKey, fetchStatus);

  return { prices, priceErr, priceStatus };
}
