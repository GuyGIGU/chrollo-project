import { useCallback, useEffect, useRef, useState } from 'react';
import { API_BASE } from '../api';

export const DEFAULT_UNIVERSE = 'us_stocks';

// Map a /screener-data/ payload to one explicit status the grid switches on.
// 'never_scanned' (valid universe, no artifact) is distinct from 'empty' (a real
// scan that matched nothing) and from 'loading'/'error'.
function deriveStatus(payload) {
  if (!payload) return 'loading';
  if (payload.status === 'never_scanned') return 'never_scanned';
  return (payload.ordered_tickers || []).length ? 'ready' : 'empty';
}

// `universe` is the single source of truth (driven by the caller, e.g. the URL).
// Payloads are cached per universe so switching back is instant and never paints
// the previous universe's setups under the new universe's label.
function useScreenerData(universe = DEFAULT_UNIVERSE) {
  const [byUniverse, setByUniverse] = useState({});
  const [status, setStatus] = useState('loading');
  const [earningsByTicker, setEarningsByTicker] = useState({});
  // Negative cache: tickers we've already asked the backend about.
  const requestedRef = useRef(new Set());
  const mountedRef = useRef(true);
  // Mirror of the per-universe cache for synchronous reads inside effects.
  const cacheRef = useRef({});
  // The universe currently selected — so a slow fetch that resolves AFTER the
  // user switched away updates only the cache (keyed, safe) and not the status
  // (which belongs to whatever universe is now on screen).
  const activeUniverseRef = useRef(universe);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const fetchScreener = useCallback(async (target) => {
    const u = target || DEFAULT_UNIVERSE;
    const isActive = () => mountedRef.current && activeUniverseRef.current === u;
    // Only blank to "loading" when we have nothing cached for this universe;
    // otherwise keep the cached payload on screen while we revalidate.
    if (!cacheRef.current[u] && isActive()) setStatus('loading');
    try {
      const response = await fetch(`${API_BASE}/screener-data/?universe=${encodeURIComponent(u)}`);
      if (!response.ok) {
        const body = await response.text().catch(() => '');
        console.error(`screener-data ${response.status}: ${body.slice(0, 200)}`);
        if (isActive()) {
          setStatus(cacheRef.current[u] ? deriveStatus(cacheRef.current[u]) : 'error');
        }
        return;
      }
      const data = await response.json();
      if (!mountedRef.current) return;
      // Cache write is always safe (keyed by u); status only if still selected.
      cacheRef.current = { ...cacheRef.current, [u]: data };
      setByUniverse(cacheRef.current);
      if (isActive()) setStatus(deriveStatus(data));
    } catch (error) {
      console.error('Failed to load screener data', error);
      if (isActive()) {
        setStatus(cacheRef.current[u] ? deriveStatus(cacheRef.current[u]) : 'error');
      }
    }
  }, []);

  // Refetch whenever the selected universe changes. Mark it active first (so a
  // late prior-universe response can't stamp its status here), set status from
  // the cached payload synchronously to avoid a stale-status frame, then fetch.
  useEffect(() => {
    activeUniverseRef.current = universe;
    const cached = cacheRef.current[universe];
    setStatus(cached ? deriveStatus(cached) : 'loading');
    fetchScreener(universe);
  }, [universe, fetchScreener]);

  // Lazy-fetch earnings for the visible page (unchanged; stable identity).
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
        missing.forEach(ticker => requestedRef.current.delete(ticker));
      });
  }, []);

  const screenerData = byUniverse[universe] || null;
  return { screenerData, status, universe, earningsByTicker, fetchScreener, fetchEarnings };
}

export default useScreenerData;
