import { useCallback, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import ScreenerModal from '../ScreenerModal';
import BridgeOut from './BridgeOut';
import usePollingInterval from '../../hooks/usePollingInterval';
import useWatchlist from '../../hooks/useWatchlist';
import { API_BASE } from '../../api';
import { tierColor } from '../../theme';

// "What needs me right now" — the cockpit's attention digest, promoting the
// urgent items out of the three zones below into one strip, ordered by urgency:
// open risk → entry fired → entry approaching → fresh top-tier idea.
//
// Trigger = the engine's `data.trigger` (the breakout level = high of the last
// LPS bar), NOT the resistance rail. "Near" = price within NEAR_PCT below it.
const NEAR_PCT = 0.02;
const STOP_RANK = { breached: 0, danger: 1, warning: 2 };
const STOP_FLAG = {
  breached: { label: 'through stop', tone: 'var(--danger)' },
  danger: { label: 'near stop', tone: 'var(--danger)' },
  warning: { label: 'watch stop', tone: 'var(--warning)' },
};
const FRESH_MAX = 8;

export default function ActionCenter({ screenerData, trades, riskFor }) {
  const { watchlist } = useWatchlist();
  const [prices, setPrices] = useState({});
  const [peek, setPeek] = useState(null);

  const chartData = screenerData?.chart_data || {};
  const ordered = screenerData?.ordered_tickers || [];
  const wlTickers = useMemo(() => [...watchlist].sort(), [watchlist]);
  const wlKey = wlTickers.join(',');

  const fetchPrices = useCallback(() => {
    if (!wlKey) return;
    fetch(`${API_BASE}/live-prices/?tickers=${encodeURIComponent(wlKey)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('prices'))))
      .then((d) => setPrices(d || {}))
      .catch(() => {});
  }, [wlKey]);
  usePollingInterval(fetchPrices, 60000);

  // Open positions through/near their stop — the only category that can't wait.
  const atRisk = useMemo(() => {
    const open = (trades || []).filter((t) => t.pnl == null && !t.closing_date && t.ticker);
    return open
      .map((t) => ({ ticker: String(t.ticker).toUpperCase(), d: riskFor(t) }))
      .filter((r) => r.d && (r.d.status === 'open' || r.d.status === 'partial') && STOP_RANK[r.d.stopRiskTone] != null)
      .sort((a, b) => STOP_RANK[a.d.stopRiskTone] - STOP_RANK[b.d.stopRiskTone]);
  }, [trades, riskFor]);

  // Watchlist names at / approaching their trigger.
  const { triggered, near } = useMemo(() => {
    const trig = [];
    const nr = [];
    for (const t of wlTickers) {
      const data = chartData[t];
      const live = prices[t];
      const trigger = data?.trigger;
      if (live == null || !Number.isFinite(Number(trigger))) continue;
      if (live >= trigger) trig.push({ t, data, live });
      else if ((trigger - live) / trigger <= NEAR_PCT) nr.push({ t, data, live, pct: (trigger - live) / trigger });
    }
    nr.sort((a, b) => a.pct - b.pct);
    return { triggered: trig, near: nr };
  }, [wlTickers, chartData, prices]);

  // Fresh top-tier ideas from the latest scan.
  const freshS = useMemo(
    () => ordered.filter((t) => chartData[t]?.tier === 'S').slice(0, FRESH_MAX),
    [ordered, chartData],
  );

  const total = atRisk.length + triggered.length + near.length + freshS.length;

  const openPeek = (t) => { if (chartData[t]) setPeek(t); };

  return (
    <section className="home-action">
      <div className="ac-head">
        <span className="ac-title">Action Center</span>
        <span className="ac-count">{total ? `${total} need${total === 1 ? 's' : ''} a look` : 'all clear'}</span>
      </div>

      {total === 0 ? (
        <div className="ac-clear">✓ Nothing needs action right now — no open risk, triggers, or fresh S-tier setups.</div>
      ) : (
        <div className="ac-groups">
          {atRisk.length > 0 && (
            <div className="ac-group">
              <span className="ac-glabel" style={{ color: 'var(--danger)' }}>⚠ At risk</span>
              {atRisk.map(({ ticker, d }) => {
                const flag = STOP_FLAG[d.stopRiskTone];
                return (
                  <Link key={ticker} to="/portfolio" className="ac-chip" style={{ borderColor: `${flag.tone}66`, color: flag.tone }}>
                    {ticker}<span className="ac-chip-sub">{flag.label}{d.distToStopPct == null ? '' : ` ${d.distToStopPct.toFixed(1)}%`}</span>
                  </Link>
                );
              })}
            </div>
          )}

          {triggered.length > 0 && (
            <div className="ac-group">
              <span className="ac-glabel" style={{ color: 'var(--success)' }}>▲ Triggered</span>
              {triggered.map(({ t, live }) => (
                <button key={t} type="button" className="ac-chip" onClick={() => openPeek(t)} style={{ borderColor: 'rgba(63,185,80,0.4)', color: 'var(--success)' }}>
                  {t}<span className="ac-chip-sub">{live.toFixed(2)}</span>
                </button>
              ))}
            </div>
          )}

          {near.length > 0 && (
            <div className="ac-group">
              <span className="ac-glabel" style={{ color: 'var(--warning)' }}>◷ Near trigger</span>
              {near.map(({ t, pct }) => (
                <button key={t} type="button" className="ac-chip" onClick={() => openPeek(t)} style={{ borderColor: 'rgba(240,190,60,0.4)', color: 'var(--warning)' }}>
                  {t}<span className="ac-chip-sub">{(pct * 100).toFixed(1)}% to trigger</span>
                </button>
              ))}
            </div>
          )}

          {freshS.length > 0 && (
            <div className="ac-group">
              <span className="ac-glabel" style={{ color: tierColor('S') }}>✦ Fresh S-tier</span>
              {freshS.map((t) => (
                <button key={t} type="button" className="ac-chip" onClick={() => openPeek(t)} style={{ borderColor: `${tierColor('S')}55`, color: tierColor('S') }}>
                  {t}<span className="ac-chip-sub">{Math.round(Number(chartData[t]?.score) || 0)}</span>
                </button>
              ))}
              <Link to="/screener" className="ac-more">grid →</Link>
            </div>
          )}
        </div>
      )}

      {peek && chartData[peek] && (
        <ScreenerModal
          ticker={peek}
          data={chartData[peek]}
          onClose={() => setPeek(null)}
          footer={<BridgeOut ticker={peek} />}
        />
      )}
    </section>
  );
}
