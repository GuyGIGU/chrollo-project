import { useCallback, useState } from 'react';
import { API_BASE } from '../../../api/base';
import usePollingInterval from '../../../shared/hooks/usePollingInterval';

/**
 * Polls /ibkr/status on the shared visibility-gated primitive, with adaptive
 * interval:
 * - Normal (connected): pollMs (default 10s)
 * - Disconnected:       3s (detect reconnection faster)
 *
 * Also exposes `dailyRestart` when IB Gateway is in its nightly restart window.
 */
export default function useIBKRStatus(pollMs = 10000) {
  const [status, setStatus] = useState({
    connected: false,
    available: false,
    mode: 'live',
    stale: false,
    daily_restart: false,
  });

  const fetchOnce = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/ibkr/status`);
      if (!r.ok) return;
      setStatus(await r.json());
    } catch { /* ignore */ }
  }, []);

  usePollingInterval(fetchOnce, status.connected ? pollMs : Math.min(pollMs, 3000));

  return status;
}
