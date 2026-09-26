import { useCallback, useEffect, useRef, useState } from 'react';
import { API_BASE } from '../../../api/base';
import usePollingInterval from '../../../shared/hooks/usePollingInterval';

/**
 * Fetch the bias-safe engine-edge summary for the Home pulse. The backend caches
 * on a short TTL, so a 5-minute client poll is plenty. Preserves last-good data
 * across a transient failure (only shows 'error' before the first success).
 */
export default function useEdgePulse(pollMs = 300000) {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState('loading'); // 'loading' | 'ready' | 'error'
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const fetchEdge = useCallback(() => {
    fetch(`${API_BASE}/engine-edge/`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`engine-edge ${r.status}`))))
      .then((d) => {
        if (!mounted.current) return;
        setData(d);
        setStatus('ready');
      })
      .catch(() => {
        if (!mounted.current) return;
        setStatus((s) => (s === 'ready' ? 'ready' : 'error')); // keep last-good once we have it
      });
  }, []);

  usePollingInterval(fetchEdge, pollMs);

  return { data, status };
}
