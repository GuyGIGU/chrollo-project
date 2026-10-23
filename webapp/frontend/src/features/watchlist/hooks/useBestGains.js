import { useEffect, useState } from 'react';
import { API_BASE } from '../../../api/base';

// The "% Best Diff" columns (GET /watchlist/best-gains): measured on the daily bars,
// so they move once a night. Fetched when the saved list changes, never polled.
// `gains` is { ticker: { status, last_bar_date, since_add, d60, d30, d14, d7, d2 } };
// a failed fetch keeps the last answer and the rows keep their dashes.
export default function useBestGains(tickersKey) {
  const [gains, setGains] = useState({});

  useEffect(() => {
    if (!tickersKey) return undefined;
    let live = true;
    fetch(`${API_BASE}/watchlist/best-gains`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`best-gains ${r.status}`))))
      .then((d) => { if (live) setGains(d || {}); })
      .catch((err) => console.warn('best gains', err));
    return () => { live = false; };
  }, [tickersKey]);

  return gains;
}
