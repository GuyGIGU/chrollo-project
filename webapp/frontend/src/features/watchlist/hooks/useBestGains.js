import { useEffect, useState } from 'react';
import { API_BASE } from '../../../api/base';

// The "% Best Diff" columns and the live columns' bases (GET /watchlist/best-gains):
// measured on the daily bars, so they move once a night. Fetched when the shown
// list changes, never polled. `week` = a past week's Monday, or null for this week.
// `gains` is { ticker: { status, last_bar_date, since_add, d60, d30, d14, d7, d2,
// basis, prev_close, dist_52w_high } }; a failed fetch keeps the last answer and
// the rows keep their dashes.
export default function useBestGains(tickersKey, week = null) {
  const [gains, setGains] = useState({ week: null, data: {} });

  useEffect(() => {
    if (!tickersKey) return undefined;
    let live = true;
    const query = week ? `?week=${encodeURIComponent(week)}` : '';
    fetch(`${API_BASE}/watchlist/best-gains${query}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`best-gains ${r.status}`))))
      .then((d) => { if (live) setGains({ week, data: d || {} }); })
      .catch((err) => console.warn('best gains', err));
    return () => { live = false; };
  }, [tickersKey, week]);

  // Another week's answer never fills this week's cells (a name can be on both lists).
  return gains.week === week ? gains.data : {};
}
