import { useCallback, useEffect, useRef, useState } from 'react';
import { API_BASE } from '../../../api/base';
import { beginLatestCall } from '../model/analyticsFold';

// The Archive's analytics: two whole-archive endpoints that take seconds each and
// ignore the table's filters, so they are fetched only while the fold is open —
// once per opening, and again after a write (refresh) while it stays open.
export default function useArchiveAnalytics(open) {
  const [calibration, setCalibration] = useState(null);
  const [equityCurve, setEquityCurve] = useState(null);
  const [status, setStatus] = useState('idle'); // 'idle' | 'loading' | 'done'
  const generation = useRef(0);

  // Only the newest call writes (beginLatestCall): an opening fetch still in flight
  // when a refresh starts must not land last with the older numbers.
  const fetchAnalytics = useCallback(async () => {
    const isLatest = beginLatestCall(generation);
    setStatus('loading');
    try {
      const [calRes, eqRes] = await Promise.all([
        fetch(`${API_BASE}/archive/calibration`),
        fetch(`${API_BASE}/archive/calibration/equity-curve`),
      ]);
      if (calRes.ok) {
        const body = await calRes.json();
        if (isLatest()) setCalibration(body);
      }
      if (eqRes.ok) {
        const body = await eqRes.json();
        if (isLatest()) setEquityCurve(body);
      }
    } catch (error) {
      console.error('Failed to fetch archive analytics:', error);
    } finally {
      if (isLatest()) setStatus('done');
    }
  }, []);

  useEffect(() => {
    if (open) fetchAnalytics();
  }, [open, fetchAnalytics]);

  // A closed fold skips the call: its next opening refetches anyway. Read through a
  // ref: Update Forward Returns can run for minutes and calls the refresh it captured
  // when clicked, so a fold opened meanwhile must still be refreshed when it ends.
  const openRef = useRef(open);
  useEffect(() => { openRef.current = open; }, [open]);
  const refresh = useCallback(() => (openRef.current ? fetchAnalytics() : Promise.resolve()), [fetchAnalytics]);

  return { calibration, equityCurve, refresh, status };
}
