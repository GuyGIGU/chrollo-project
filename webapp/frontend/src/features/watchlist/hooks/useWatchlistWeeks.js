import { useEffect, useState } from 'react';
import { API_BASE } from '../../../api/base';

// The week switcher's data. This week's list lives in the watchlist store; a
// past week is read-only history, so it is fetched here and never stored.

// { current, weeks }: this week's Monday and every week with a list, newest
// first (GET /watchlist/weeks). Refetched when this week's list changes, so a
// list that rolled over after Friday's scan shows up without a reload.
export function useWatchlistWeeks(refreshKey) {
  const [weeks, setWeeks] = useState({ current: null, weeks: [] });
  useEffect(() => {
    let live = true;
    fetch(`${API_BASE}/watchlist/weeks`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`weeks ${r.status}`))))
      .then((d) => { if (live) setWeeks({ current: d?.current ?? null, weeks: d?.weeks || [] }); })
      .catch((err) => console.warn('watchlist weeks', err));
    return () => { live = false; };
  }, [refreshKey]);
  return weeks;
}

const IDLE = { week: null, records: [], status: 'idle' };

// A past week's list as it ended (GET /watchlist/?week=). `week` null = none.
export function usePastWeek(week) {
  const [state, setState] = useState(IDLE);
  useEffect(() => {
    if (!week) return undefined;
    let live = true;
    fetch(`${API_BASE}/watchlist/?week=${encodeURIComponent(week)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`week ${r.status}`))))
      .then((records) => { if (live) setState({ week, records: records || [], status: 'ready' }); })
      .catch((err) => {
        console.warn('watchlist past week', err);
        if (live) setState({ week, records: [], status: 'error' });
      });
    return () => { live = false; };
  }, [week]);
  // Until this week's answer lands, say loading rather than show another week's rows.
  if (!week) return IDLE;
  return state.week === week ? state : { week, records: IDLE.records, status: 'loading' };
}
