import { useCallback, useEffect, useMemo, useState } from 'react';
import { API_BASE } from '../api';
import useIBKRStatus from './useIBKRStatus';
import usePollingInterval from './usePollingInterval';
import { deriveTradeRow } from '../utils/tradeTableUtils';

// Single frontend source for live open-trade risk. The backend (`GET /live-risk`)
// is the canonical risk-math implementation; this hook owns the poll and exposes
// a `riskFor(trade)` accessor that mirrors the old `deriveTradeRow(trade, priceFor)`
// return shape, so consumers swap one call for another. Mount it ONCE at the
// trades-data owner (AppShell) and thread `riskFor`/`summary` down — never a fetch
// per consumer.
//
// riskFor(trade) returns the server-derived row for an OPEN trade (live overlay);
// for a closed/draft trade the server doesn't price, OR while a poll is in flight,
// it falls back to the price-INDEPENDENT client derivation (`deriveTradeRow`), which
// is byte-identical to the old behavior for settled trades and degrades an open row
// to "no quote" cleanly.

const EMPTY_SUMMARY = {
  nOpen: 0,
  nPriced: 0,
  totalUnrealizedPnl: null,
  nBreached: 0,
  nDanger: 0,
  nWarning: 0,
  nAtRisk: 0,
};

export default function useLiveRisk(trades) {
  const [rows, setRows] = useState({});
  const [summary, setSummary] = useState(EMPTY_SUMMARY);
  const [status, setStatus] = useState('idle');
  const ibkrStatus = useIBKRStatus(10000);
  const ibkrConnected = Boolean(ibkrStatus?.connected);

  // Stable key over the OPEN-candidate trade ids so the poll interval is not
  // reset on every parent render (the open set, not the array identity, is what
  // "changed" means here — mirrors useTradeLivePrices' joined-string key).
  const openKey = useMemo(() => {
    const ids = [];
    for (const trade of trades || []) {
      if (trade && trade.pnl == null && !trade.closing_date && trade.ticker) ids.push(trade.id);
    }
    return ids.sort((a, b) => a - b).join(',');
  }, [trades]);

  const hasOpen = openKey.length > 0;

  const fetchRisk = useCallback(() => {
    if (!hasOpen) {
      setRows({});
      setSummary(EMPTY_SUMMARY);
      setStatus('ready');
      return;
    }
    setStatus((current) => (current === 'ready' || current === 'stale' ? current : 'loading'));
    // fetch does not reject on 4xx/5xx — guard response.ok before json().
    fetch(`${API_BASE}/live-risk/`)
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error('live-risk'))))
      .then((data) => {
        setRows(data?.rows || {});
        setSummary(data?.summary || EMPTY_SUMMARY);
        setStatus(data?.stale ? 'stale' : 'ready');
      })
      .catch(() => setStatus('error'));
  }, [hasOpen]);

  // Visibility-gated poll (pauses on a hidden tab); cadence matches the legacy
  // live-price poll — slower when IBKR pushes, faster on the yfinance fallback.
  usePollingInterval(fetchRisk, hasOpen ? (ibkrConnected ? 60000 : 20000) : null);

  // Refetch immediately when the open set changes (a position opened/closed), so
  // a new position is priced without waiting a whole interval.
  useEffect(() => {
    fetchRisk();
  }, [openKey, fetchRisk]);

  const riskFor = useCallback((trade) => {
    if (!trade) return null;
    const serverRow = rows[trade.id];
    if (serverRow) return serverRow;
    return deriveTradeRow(trade);
  }, [rows]);

  return { riskFor, summary, status };
}
