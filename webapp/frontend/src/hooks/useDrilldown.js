import { useCallback, useRef, useState } from 'react';
import { API_BASE } from '../api';

// Owns the top-down drill-down fetch (a firing sector/commodity ETF -> its
// related US-stock setups), mirroring useScreenerData's status shape instead of
// hand-rolling a second fetch path inside the grid. A request token guards
// against stale resolves: clicking Back or a second ETF before the first lands
// must not resurrect or cross-paint the view.
//
// `drilldown` is null when closed, else { etf, status, basis, ordered_tickers,
// chart_data }, where status ∈ loading | ready | empty | error.
function useDrilldown() {
  const [drilldown, setDrilldown] = useState(null);
  const requestRef = useRef(0);
  const mountedRef = useRef(true);

  const open = useCallback((etf) => {
    const token = ++requestRef.current;
    setDrilldown({ etf, status: 'loading', ordered_tickers: [], chart_data: {} });
    fetch(`${API_BASE}/screener-data/drilldown/?etf=${encodeURIComponent(etf)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('drilldown'))))
      .then((d) => {
        // Ignore if a newer open()/close() superseded this request.
        if (!mountedRef.current || token !== requestRef.current) return;
        const n = (d.ordered_tickers || []).length;
        setDrilldown({ ...d, status: n ? 'ready' : 'empty' });
      })
      .catch(() => {
        if (!mountedRef.current || token !== requestRef.current) return;
        setDrilldown({ etf, status: 'error', basis: 'error', ordered_tickers: [], chart_data: {} });
      });
  }, []);

  // Invalidate any in-flight request so a late response can't reopen the view.
  const close = useCallback(() => {
    requestRef.current += 1;
    setDrilldown(null);
  }, []);

  // React strict-mode/unmount guard (one-time).
  if (typeof window !== 'undefined') mountedRef.current = true;

  return { drilldown, openDrilldown: open, closeDrilldown: close };
}

export default useDrilldown;
