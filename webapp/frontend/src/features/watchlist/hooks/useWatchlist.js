import { useEffect, useSyncExternalStore } from 'react';
import {
  fetchWatchlist,
  getWatchlistActiveSet,
  subscribeWatchlistStore,
  toggleWatchlist,
} from './watchlistStore';

// Contract unchanged: { watchlist: Set<ticker>, toggleWatchlist(ticker,
// saveContext?) }. Now store-backed (Finviz plan Task 8): the four mounts
// (ScreenerGrid, WatchlistZone, ActionCenter, useLivePrices) share one records
// list, so a star on the Screener is instantly visible on Home. The optional
// saveContext = { universe, scanDate } carries the DISPLAYED scan identity so
// the server pins the artifact the operator was actually looking at (EC-37).
function useWatchlist() {
  const watchlist = useSyncExternalStore(subscribeWatchlistStore, getWatchlistActiveSet);

  useEffect(() => {
    fetchWatchlist(); // in-flight dedup'd across the four mounts
  }, []);

  return { watchlist, toggleWatchlist };
}

export default useWatchlist;
