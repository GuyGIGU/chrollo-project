import { useEffect, useState, useRef } from 'react';
import { API_BASE } from '../api';

/**
 * Polls /ibkr/status with adaptive interval:
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
  const statusRef = useRef(status);
  statusRef.current = status;

  useEffect(() => {
    let cancelled = false;
    let intervalId = null;

    const fetchOnce = async () => {
      try {
        const r = await fetch(`${API_BASE}/ibkr/status`);
        if (!r.ok) return;
        const j = await r.json();
        if (!cancelled) {
          setStatus(j);
          // Reschedule with adaptive interval
          reschedule(j.connected);
        }
      } catch { /* ignore */ }
    };

    const reschedule = (isConnected) => {
      if (intervalId) clearInterval(intervalId);
      const interval = isConnected ? pollMs : Math.min(pollMs, 3000);
      intervalId = setInterval(fetchOnce, interval);
    };

    // Kick off the first fetch; reschedule() inside will set up the interval
    fetchOnce();

    return () => {
      cancelled = true;
      if (intervalId) clearInterval(intervalId);
    };
  }, [pollMs]);

  return status;
}
