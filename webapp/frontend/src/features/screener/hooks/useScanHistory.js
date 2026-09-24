import { useState } from 'react';
import { API_BASE } from '../../../api/base';

// The ONE fetcher for the scan-run diagnostics registry, owned by AppShell so
// the topbar pills and the Archive header's Scan History button open the same
// modal instance. Fetch-on-open (not polled), so the registry can never show a
// reason a minute staler than the pill beside it.
//
// kind=all widens past the screener scan to the outcome backfill and the
// market-data download, whose failures have never surfaced anywhere.
export default function useScanHistory() {
  const [open, setOpen] = useState(false);
  const [runs, setRuns] = useState(null);
  const [notice, setNotice] = useState(null);
  const [loading, setLoading] = useState(false);

  const openHistory = async () => {
    setOpen(true);
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/scan-status/history?limit=25&kind=all`);
      const data = await response.json().catch(() => ({}));
      setRuns(Array.isArray(data.runs) ? data.runs : []);
      setNotice(typeof data.notice === 'string' ? data.notice : null);
    } catch (error) {
      console.error('Failed to fetch scan history:', error);
      setRuns([]);
      setNotice(null);
    } finally {
      setLoading(false);
    }
  };

  return { open, runs, notice, loading, openHistory, closeHistory: () => setOpen(false) };
}
