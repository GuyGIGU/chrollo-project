import { useRef, useState } from 'react';
import { API_BASE } from '../api';

// Free (ticker, as-of) chart lookup for the Calibration page. One hook owns
// data / loading / failure state (the useArchiveChart mold), plus the
// per-sitting cache: every (ticker, as-of-session) response is kept in a ref
// Map so revisits — the day-scrub gesture, Prev/Next hops — are instant and
// never re-hit the vendor. Failures carry the endpoint's {class, message}
// so the page can render a SPECIFIC, actionable state per failure class.
export default function useCalibrationChart() {
  const [chartData, setChartData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [failure, setFailure] = useState(null); // {class, message} | null
  const cacheRef = useRef(new Map());

  const load = async (ticker, asOf) => {
    const key = `${(ticker || '').trim().toUpperCase()}|${asOf}`;
    const cached = cacheRef.current.get(key);
    if (cached) {
      setChartData(cached);
      setFailure(null);
      return cached;
    }
    setLoading(true);
    setFailure(null);
    try {
      const params = new URLSearchParams({ ticker, as_of: asOf });
      const response = await fetch(`${API_BASE}/calibration/chart?${params}`);
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = body?.detail;
        setFailure(detail?.class
          ? detail
          : { class: 'unknown', message: `lookup failed (${response.status})` });
        setChartData(null);
        return null;
      }
      if (!Array.isArray(body?.candles)) {
        // A 200 that isn't a chart payload: the running service predates the
        // calibration endpoint (its SPA catch-all answers unknown paths with
        // index.html). Never cache it — surface the one action that fixes it.
        setFailure({
          class: 'service_stale',
          message: 'the running dashboard service does not know /calibration yet',
        });
        setChartData(null);
        return null;
      }
      cacheRef.current.set(key, body);
      // The resolved session is the response's identity too — a Sunday and
      // its Friday resolve to one payload; cache both keys.
      if (body?.as_of_session && body.as_of_session !== asOf) {
        cacheRef.current.set(`${body.ticker}|${body.as_of_session}`, body);
      }
      setChartData(body);
      return body;
    } catch (error) {
      console.error('calibration chart lookup failed:', error);
      setFailure({ class: 'network', message: 'backend unreachable — is the service running?' });
      setChartData(null);
      return null;
    } finally {
      setLoading(false);
    }
  };

  const clear = () => {
    setChartData(null);
    setFailure(null);
  };

  return { chartData, loading, failure, load, clear };
}
