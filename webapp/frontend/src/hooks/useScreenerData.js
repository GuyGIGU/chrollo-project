import { useCallback, useEffect, useSyncExternalStore } from 'react';
import {
  DEFAULT_UNIVERSE,
  fetchScreenerEarnings,
  fetchScreenerUniverse,
  revalidateScreenerUniverse,
  getScreenerEarnings,
  getScreenerPayload,
  getScreenerStatus,
  subscribeScreenerStore,
} from './screenerStore';

export { DEFAULT_UNIVERSE };

// Thin subscription over the module-level screenerStore — the cache, in-flight
// dedup, and status/stale-token semantics live there, shared across every hook
// instance. `universe` is the single source of truth (driven by the caller,
// e.g. the URL); switching back to a cached universe paints instantly while a
// background revalidate runs.
function useScreenerData(universe = DEFAULT_UNIVERSE) {
  const screenerData = useSyncExternalStore(subscribeScreenerStore, () => getScreenerPayload(universe));
  const status = useSyncExternalStore(subscribeScreenerStore, () => getScreenerStatus(universe));
  const earningsByTicker = useSyncExternalStore(subscribeScreenerStore, getScreenerEarnings);

  // Revalidate whenever the selected universe changes (also the initial fetch).
  // Summary-first: a cached universe only re-downloads the full multi-MB
  // artifact when scanned_at moved; an uncached one falls back to the full fetch.
  useEffect(() => {
    revalidateScreenerUniverse(universe);
  }, [universe]);

  // Explicit calls (scan runner after a scan, retry buttons) always hit the
  // network — matching the old hook — even if a background revalidate is in flight.
  const fetchScreener = useCallback((target) => fetchScreenerUniverse(target || DEFAULT_UNIVERSE, { fresh: true }), []);
  const fetchEarnings = useCallback((visibleTickers) => fetchScreenerEarnings(visibleTickers), []);

  return { screenerData, status, universe, earningsByTicker, fetchScreener, fetchEarnings };
}

export default useScreenerData;
