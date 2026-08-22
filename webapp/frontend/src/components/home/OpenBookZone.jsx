import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import HomeZone from './HomeZone';
import { PortfolioIcon } from '../NavIcons';
import { fmtMoney } from '../../utils/tradeTableUtils';
import { finiteOrNull } from '../../utils/format.js';

const ICON = <PortfolioIcon className="home-zone-iconsvg" />;

// One quiet placeholder for genuine absence (no live quote / no value); the
// distinct "no stop recorded" state gets its own affordance below.
const DASH = '—';

// Open risk reads first: a position through/near its stop out-ranks its
// alphabetical slot, so the eye lands on what can't wait.
const RISK_RANK = { breached: 0, danger: 1, warning: 2 };

const FLAG = {
  breached: { label: 'through stop', color: 'var(--danger)' },
  danger: { label: 'near stop', color: 'var(--danger)' },
  warning: { label: 'watch stop', color: 'var(--warning)' },
};

const NO_STOP = 'No stop recorded — R and distance need a stop.';

// Live price provenance: a live broker/quote feed vs. a stale last-known print.
const priceMeta = (source) => {
  if (source === 'ibkr') return { label: 'IBKR', live: true };
  if (source === 'yf') return { label: 'LIVE', live: true };
  if (source === 'fills') return { label: 'last', live: false };
  return { label: null, live: false };
};

const signed = (value, suffix, digits) => {
  const n = finiteOrNull(value);
  if (n == null) return null;
  return `${n >= 0 ? '+' : '−'}${Math.abs(n).toFixed(digits)}${suffix}`;
};

// Distinguish a loading / errored live-risk feed from a genuinely flat book —
// never tell a trader carrying live risk that they have no positions.
const emptyMessage = (status) => {
  if (status === 'loading' || status === 'idle') return 'Checking open positions…';
  if (status === 'error') return 'Live risk unavailable — retrying.';
  return 'No open positions.';
};

export default function OpenBookZone({ trades, riskFor, status }) {
  const link = <Link className="home-zone-link" to="/portfolio">Open Portfolio →</Link>;

  const rows = useMemo(() => {
    const open = (trades || []).filter((t) => t.pnl == null && !t.closing_date && t.ticker);
    return open
      .map((t) => ({ trade: t, d: riskFor(t) }))
      .filter((r) => r.d && (r.d.status === 'open' || r.d.status === 'partial'))
      .sort((a, b) => {
        const ra = RISK_RANK[a.d.stopRiskTone] ?? 9;
        const rb = RISK_RANK[b.d.stopRiskTone] ?? 9;
        if (ra !== rb) return ra - rb;
        return String(a.trade.ticker).localeCompare(String(b.trade.ticker));
      });
  }, [trades, riskFor]);

  if (rows.length === 0) {
    return <HomeZone title="Open Book" icon={ICON} link={link} status="empty" empty={emptyMessage(status)} />;
  }

  const atRisk = rows.filter((r) => FLAG[r.d.stopRiskTone]).length;
  const unpriced = rows.filter((r) => r.d.currentExit == null).length;
  const feedStale = status === 'stale' || status === 'error';

  return (
    <HomeZone title="Open Book" icon={ICON} link={link} status="ready">
      {(atRisk > 0 || unpriced > 0 || feedStale) && (
        <div className="home-ob-head">
          {atRisk > 0 && <span className="home-ob-atrisk">{atRisk} at risk</span>}
          {unpriced > 0 && <span className="home-ob-note">{rows.length - unpriced}/{rows.length} priced</span>}
          {feedStale && <span className="home-ob-note home-ob-stale">stale feed</span>}
        </div>
      )}
      <div className="home-ob">
        {rows.map(({ trade, d }) => {
          const pnlColor = d.pnl == null ? 'var(--text-faint)' : d.pnl >= 0 ? 'var(--success)' : 'var(--danger)';
          const flag = FLAG[d.stopRiskTone] || null;
          const stopColor = flag ? flag.color : 'var(--text-muted)';
          const meta = priceMeta(d.currentExitSource);
          const hasStop = d.stopVal != null;
          return (
            <div key={trade.id} className="home-ob-row">
              <span className="home-ob-cell">
                <span className="home-ob-name">{String(trade.ticker).toUpperCase()}</span>
                <span className={`home-ob-sub ${meta.live ? '' : 'home-ob-faint'}`} title={meta.label ? `Price source: ${meta.label}` : 'No live quote'}>
                  {d.currentExit == null ? DASH : `$${fmtMoney(d.currentExit)}`}
                </span>
              </span>

              <span className="home-ob-cell home-ob-num">
                <span className="home-ob-pnl" style={{ color: pnlColor }}>
                  {d.pnl == null ? DASH : `${d.pnl >= 0 ? '+' : '−'}$${fmtMoney(Math.abs(d.pnl))}`}
                </span>
                <span className="home-ob-sub" style={{ color: d.pnlPct == null ? 'var(--text-faint)' : pnlColor }}>
                  {signed(d.pnlPct, '%', 1) ?? DASH}
                </span>
              </span>

              <span className="home-ob-cell home-ob-num">
                <span className="home-ob-r" title={hasStop ? 'R-multiple' : NO_STOP}>
                  {d.rValue == null ? DASH : `${d.rValue.toFixed(2)}R`}
                </span>
              </span>

              <span className="home-ob-cell home-ob-num">
                {hasStop ? (
                  <>
                    <span className="home-ob-stop" style={{ color: stopColor }} title="Distance to stop">
                      {d.distToStopPct == null ? DASH : `${d.distToStopPct.toFixed(1)}%`}
                    </span>
                    <span className="home-ob-sub" style={{ color: flag ? stopColor : 'var(--text-faint)' }}>
                      {d.distToStopR == null ? DASH : `${d.distToStopR.toFixed(2)}R`}
                    </span>
                  </>
                ) : (
                  <span className="home-ob-nostop" title={NO_STOP}>no stop</span>
                )}
              </span>

              {flag
                ? <span className="home-ob-flag" style={{ color: flag.color, borderColor: flag.color }}>{flag.label}</span>
                : <span className="home-ob-flag" />}
            </div>
          );
        })}
      </div>
    </HomeZone>
  );
}
