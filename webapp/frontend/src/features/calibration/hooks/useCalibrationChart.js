import { useRef, useState } from 'react';
import { API_BASE } from '../../../api/base';
import {
  cacheKey,
  cacheKeysFor,
  classifyChartResponse,
  normalizeTicker,
} from '../model/calibrationChartUtils';

// Free (ticker, as-of) chart lookup for the Calibration page. One hook owns
// data / loading / failure state, hardened per Council Review 2026-07-11
// finding 10:
// * The sitting cache lives at MODULE scope — a mid-sitting hop to another
//   tab and back keeps every cached lookup (single-operator localhost app).
// * In-flight requests dedupe: a double-clicked scrub is one vendor fetch.
// * A request generation guards racing responses — the LATEST lookup wins,
//   never the last to arrive.
// * A failure keeps the last good chart on screen (failure renders as an
//   overlay); only a successful lookup replaces chartData.
const chartCache = new Map();     // key -> chart payload (real payloads only)
const inflight = new Map();       // key -> pending fetch promise

async function fetchChart(ticker, asOf) {
  try {
    const params = new URLSearchParams({ ticker, as_of: asOf });
    const response = await fetch(`${API_BASE}/calibration/chart?${params}`, {
      headers: { 'X-Chrollo-Client': 'chrollo-dashboard' },
    });
    const body = await response.json().catch(() => null);
    return classifyChartResponse(response.ok, response.status, body);
  } catch (error) {
    console.error('calibration chart lookup failed:', error);
    return {
      kind: 'failure',
      failure: { class: 'network', message: 'backend unreachable — is the service running?' },
    };
  }
}

export default function useCalibrationChart() {
  const [chartData, setChartData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [failure, setFailure] = useState(null); // {class, message} | null
  const generation = useRef(0);
  const shownRef = useRef(null);

  const load = async (ticker, asOf) => {
    const symbol = normalizeTicker(ticker);
    const key = cacheKey(symbol, asOf);
    const gen = ++generation.current;

    const cached = chartCache.get(key);
    if (cached) {
      setFailure(null);
      setLoading(false);
      // Re-loading the key already on screen must still re-render (the
      // chart errorFallback's "Reload the lookup" recovery) — same-reference
      // setState is a React bailout, so hand out a fresh identity then.
      setChartData(shownRef.current === cached ? { ...cached } : cached);
      shownRef.current = cached;
      return cached;
    }

    setLoading(true);
    setFailure(null);
    let pending = inflight.get(key);
    if (!pending) {
      pending = fetchChart(symbol, asOf).finally(() => inflight.delete(key));
      inflight.set(key, pending);
    }
    const result = await pending;
    if (gen !== generation.current) return null; // superseded — a newer lookup owns the state
    setLoading(false);
    if (result.kind === 'chart') {
      for (const k of cacheKeysFor(key, result.body)) chartCache.set(k, result.body);
      setFailure(null);
      setChartData(result.body);
      shownRef.current = result.body;
      return result.body;
    }
    setFailure(result.failure); // last good chart stays up — overlay, not wipe
    return null;
  };

  const clear = () => {
    setChartData(null);
    setFailure(null);
    shownRef.current = null;
  };

  return { chartData, loading, failure, load, clear };
}
