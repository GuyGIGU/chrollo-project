import { useCallback, useEffect, useRef, useState } from 'react';
import { API_BASE } from '../api';

function useScreenerData() {
  const [screenerData, setScreenerData] = useState(null);
  const [earningsByTicker, setEarningsByTicker] = useState({});
  // Negative cache: tickers we've already asked the backend about, so a name the
  // backend has no earnings record for is requested once instead of forever.
  const requestedRef = useRef(new Set());
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const fetchScreener = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/screener-data/`);
      if (response.ok) {
        const data = await response.json();
        if (mountedRef.current) setScreenerData(data);
        return;
      }
      const body = await response.text().catch(() => '');
      console.error(`screener-data ${response.status}: ${body.slice(0, 200)}`);
    } catch (error) {
      console.error('Failed to load screener data', error);
    }
  }, []);

  useEffect(() => {
    fetchScreener();
  }, [fetchScreener]);

  // Lazy-fetch earnings for the visible page. fetchEarnings has a stable identity
  // (no deps) so merging results never re-fires the caller's effect, and the
  // negative cache prevents an endless refetch loop when the backend omits a
  // ticker. setState is guarded so a late response after unmount is dropped.
  const fetchEarnings = useCallback((visibleTickers) => {
    const missing = visibleTickers.filter(ticker => !requestedRef.current.has(ticker));
    if (missing.length === 0) return;
    missing.forEach(ticker => requestedRef.current.add(ticker));
    fetch(`${API_BASE}/screener-data/earnings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tickers: missing }),
    })
      .then(response => response.ok ? response.json() : {})
      .then(data => {
        if (mountedRef.current) setEarningsByTicker(previous => ({ ...previous, ...data }));
      })
      .catch(() => {
        // Network failure (not a missing record): allow a retry on a later render.
        missing.forEach(ticker => requestedRef.current.delete(ticker));
      });
  }, []);

  return { screenerData, earningsByTicker, fetchScreener, fetchEarnings };
}

export default useScreenerData;
