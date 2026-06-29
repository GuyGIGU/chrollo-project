import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import HomeZone from './HomeZone';
import { JournalIcon } from '../NavIcons';
import EquityCurve from '../EquityCurve';

// Journal Pulse — a live read of the realized book: the equity curve plus the
// four figures that frame it. Reuses EquityCurve (self-fetching) and the
// shell-owned /stats payload; this tile never recomputes outcomes, it formats.
const money = (v) => {
  if (v == null || !Number.isFinite(Number(v))) return '—';
  const n = Number(v);
  const sign = n < 0 ? '−' : '';
  return `${sign}$${Math.abs(n).toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
};
const pct1 = (v) => (Number.isFinite(Number(v)) ? `${Number(v).toFixed(1)}%` : '—');

export default function JournalPulseZone({ stats, trades }) {
  const link = <Link className="home-zone-link" to="/dashboard">Open Journal →</Link>;
  const icon = <JournalIcon className="home-zone-iconsvg" />;

  const view = useMemo(() => {
    const s = stats || {};
    const closed = (trades || []).filter((t) => t.pnl != null && t.pnl !== undefined).length;
    return {
      pnl: Number(s.total_pnl) || 0,
      winRate: s.win_rate,
      total: s.total_trades ?? (trades || []).length ?? 0,
      avgWin: s.avg_win,
      avgLoss: s.avg_loss,
      closed,
    };
  }, [stats, trades]);

  if (view.total === 0) {
    return (
      <HomeZone title="Journal Pulse" icon={icon} link={link} status="empty"
        empty="No trades logged yet." />
    );
  }

  const pnlColor = view.pnl >= 0 ? 'var(--success)' : 'var(--danger)';

  return (
    <HomeZone title="Journal Pulse" icon={icon} link={link} status="ready">
      <div className="home-jp">
        <div className="home-jp-figs">
          <div className="home-jp-fig">
            <span className="home-jp-val" style={{ color: pnlColor }}>{money(view.pnl)}</span>
            <span className="home-jp-lbl">net P&amp;L</span>
          </div>
          <div className="home-jp-fig">
            <span className="home-jp-val">{pct1(view.winRate)}</span>
            <span className="home-jp-lbl">win rate</span>
          </div>
          <div className="home-jp-fig">
            <span className="home-jp-val">{view.total}</span>
            <span className="home-jp-lbl">trades</span>
          </div>
        </div>
        <div className="home-jp-chart">
          <EquityCurve />
        </div>
        <div className="home-jp-avgs">
          <span>Avg W <b style={{ color: 'var(--success)' }}>{money(view.avgWin)}</b></span>
          <span>Avg L <b style={{ color: 'var(--danger)' }}>{view.avgLoss == null ? '—' : `−$${Math.abs(Number(view.avgLoss)).toLocaleString('en-US', { maximumFractionDigits: 0 })}`}</b></span>
        </div>
      </div>
    </HomeZone>
  );
}
