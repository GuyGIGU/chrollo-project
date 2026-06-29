import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import HomeZone from './HomeZone';
import { PortfolioIcon } from '../NavIcons';
import { deriveTradeRow, fmtMoney } from '../../utils/tradeTableUtils';

const ICON = <PortfolioIcon className="home-zone-iconsvg" />;

// Open risk reads first: a position through/near its stop out-ranks its
// alphabetical slot, so the eye lands on what can't wait.
const RISK_RANK = { breached: 0, danger: 1, warning: 2 };

const FLAG = {
  breached: { label: 'through stop', color: 'var(--danger)' },
  danger: { label: 'near stop', color: 'var(--danger)' },
  warning: { label: 'watch stop', color: 'var(--warning)' },
};

export default function OpenBookZone({ trades, priceFor }) {
  const link = <Link className="home-zone-link" to="/portfolio">Open Portfolio →</Link>;

  const rows = useMemo(() => {
    const open = (trades || []).filter((t) => t.pnl == null && !t.closing_date && t.ticker);
    return open
      .map((t) => ({ trade: t, d: deriveTradeRow(t, priceFor) }))
      .filter((r) => r.d && (r.d.status === 'open' || r.d.status === 'partial'))
      .sort((a, b) => {
        const ra = RISK_RANK[a.d.stopRiskTone] ?? 9;
        const rb = RISK_RANK[b.d.stopRiskTone] ?? 9;
        if (ra !== rb) return ra - rb;
        return String(a.trade.ticker).localeCompare(String(b.trade.ticker));
      });
  }, [trades, priceFor]);

  if (rows.length === 0) {
    return <HomeZone title="Open Book" icon={ICON} link={link} status="empty" empty="No open positions." />;
  }

  return (
    <HomeZone title="Open Book" icon={ICON} link={link} status="ready">
      <div className="home-ob">
        {rows.map(({ trade, d }) => {
          const stale = d.currentExit == null || d.currentExitSource == null;
          const pnlColor = d.pnl == null ? 'var(--text-faint)' : d.pnl >= 0 ? 'var(--success)' : 'var(--danger)';
          const flag = FLAG[d.stopRiskTone] || null;
          return (
            <div key={trade.id} className="home-ob-row">
              <span className="home-ob-name">{String(trade.ticker).toUpperCase()}</span>
              <span className="home-ob-pnl" style={{ color: pnlColor }}>
                {d.pnl == null ? '—' : `${d.pnl >= 0 ? '+' : '−'}$${fmtMoney(Math.abs(d.pnl))}`}
              </span>
              <span className="home-ob-r" title="R-multiple">
                {d.rValue == null ? '·' : `${d.rValue.toFixed(2)}R`}
              </span>
              <span
                className="home-ob-stop"
                title="distance to stop"
                style={{ color: flag ? flag.color : 'var(--text-muted)' }}
              >
                {d.distToStopPct == null ? '·' : `${d.distToStopPct.toFixed(1)}%`}
              </span>
              {flag
                ? <span className="home-ob-flag" style={{ color: flag.color, borderColor: flag.color }}>{flag.label}</span>
                : <span className="home-ob-flag">{stale ? <span className="home-wl-stale">stale</span> : null}</span>}
            </div>
          );
        })}
      </div>
    </HomeZone>
  );
}
