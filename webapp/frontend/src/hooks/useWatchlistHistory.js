import { useCallback, useEffect, useState } from 'react';
import { API_BASE } from '../api';

// Read-only weekly-review data (Finviz plan Task 8): a separate history hook
// beside the membership store — it refetches when its surface is shown and
// never writes. Weeks arrive grouped server-side by the pinned scan_date's
// ISO week (EC-28: the grouping is a resolved verdict, not client math).
export function useWatchlistHistory(visible) {
  const [weeks, setWeeks] = useState(null); // null = loading, [] = no history
  const [error, setError] = useState(false);

  const reload = useCallback(() => {
    fetch(`${API_BASE}/watchlist/review?limit_weeks=26`)
      .then((response) => {
        if (!response.ok) throw new Error(`watchlist review ${response.status}`);
        return response.json();
      })
      .then((data) => {
        setWeeks(data.weeks || []);
        setError(false);
      })
      .catch((err) => {
        console.error('Watchlist review load failed', err);
        setError(true);
      });
  }, []);

  useEffect(() => {
    if (visible) reload();
  }, [visible, reload]);

  return { weeks, error, reload };
}

export function fetchReplay(watchId) {
  return fetch(`${API_BASE}/watchlist/${watchId}/replay`).then((response) => {
    if (!response.ok) throw new Error(`watchlist replay ${response.status}`);
    return response.json();
  });
}
