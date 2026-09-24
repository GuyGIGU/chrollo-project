import { useCallback, useEffect, useState } from 'react';
import { API_BASE } from '../../../api/base';
import usePollingInterval from '../../../shared/hooks/usePollingInterval';

function useDashboardData() {
  const [trades, setTrades] = useState([]);
  const [stats, setStats] = useState(null);
  const [scanStatus, setScanStatus] = useState(null);
  const [health, setHealth] = useState(null);

  const fetchDashboardData = useCallback(async () => {
    try {
      // Independent endpoints — fire both at once so load time is the slower of
      // the two round-trips, not their sum.
      const [tradesRes, statsRes] = await Promise.all([
        fetch(`${API_BASE}/trades/`),
        fetch(`${API_BASE}/journal-stats/`),
      ]);
      if (tradesRes.ok) {
        setTrades(await tradesRes.json());
      }
      if (statsRes.ok) {
        setStats(await statsRes.json());
      }
    } catch (error) {
      console.error('Error fetching data:', error);
    }
  }, []);

  const fetchScanStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/scan-status/latest`);
      if (res.ok) {
        setScanStatus(await res.json());
      }
    } catch (error) {
      console.error('Error fetching scan status:', error);
    }
  }, []);

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (res.ok) {
        setHealth(await res.json());
      }
    } catch (error) {
      console.error('Error fetching health:', error);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  // Visibility-gated pollers (immediate first tick covers the mount fetch).
  usePollingInterval(fetchScanStatus, 60000);
  usePollingInterval(fetchHealth, 60000);

  return {
    trades,
    stats,
    scanStatus,
    health,
    fetchDashboardData,
  };
}

export default useDashboardData;
