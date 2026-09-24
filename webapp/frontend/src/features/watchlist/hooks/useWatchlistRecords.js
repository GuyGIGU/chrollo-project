import { useEffect, useSyncExternalStore } from 'react';
import {
  fetchWatchlist,
  getWatchlistRecords,
  subscribeWatchlistStore,
} from './watchlistStore';

// The dated active-save records ({ticker, created_at, save_date, pinned,
// pin_scan_date}) from the shared watchlist store — for surfaces that render
// more than membership (the Home table's saved-age column). Same store as
// useWatchlist, so a star toggled anywhere updates these rows too.
export default function useWatchlistRecords() {
  const records = useSyncExternalStore(subscribeWatchlistStore, getWatchlistRecords);

  useEffect(() => {
    fetchWatchlist(); // in-flight dedup'd with every other mount
  }, []);

  return records;
}
