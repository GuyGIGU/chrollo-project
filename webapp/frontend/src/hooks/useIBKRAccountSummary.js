import { useEffect, useState } from 'react';
import { API_BASE } from '../api';

/**
 * Polls /portfolio/account-summary while IBKR is connected.
 * Returns { values, currency } — see backend.portfolio._flatten_summary.
 * Falls back to nulls when disconnected; caller should check for presence.
 */
export default function useIBKRAccountSummary(connected, pollMs = 8000) {
  const [data, setData] = useState({ values: {}, currency: {} });

  useEffect(() => {
    if (!connected) return;
    let cancelled = false;

    const fetchOnce = async () => {
      try {
        const r = await fetch(`${API_BASE}/portfolio/account-summary`);
        if (!r.ok) return;
        const j = await r.json();
        if (!cancelled) setData({ values: j.values || {}, currency: j.currency || {} });
      } catch { /* ignore */ }
    };

    fetchOnce();
    const id = setInterval(fetchOnce, pollMs);
    return () => { cancelled = true; clearInterval(id); };
  }, [connected, pollMs]);

  return data;
}
