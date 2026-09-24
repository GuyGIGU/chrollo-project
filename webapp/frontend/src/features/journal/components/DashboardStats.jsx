import React from 'react';
import EquityCurve from './EquityCurve';
import { fx } from '../../../shared/formatting/format';

const DashboardStats = ({ stats, trades = [], activeFilter, onFilterChange }) => {
  const data = stats || {
    winning_trades: 0,
    losing_trades: 0,
    win_rate: 0,
    avg_win: 0,
    avg_loss: 0,
    total_pnl: 0,
    total_trades: 0,
  };

  const openCount = trades.filter(t => t.pnl === null || t.pnl === undefined).length;
  const washCount = trades.filter(t => t.pnl === 0).length;
  const total = data.total_trades || trades.length || 0;
  const openPct = total ? (openCount / total) * 100 : 0;
  const washPct = total ? (washCount / total) * 100 : 0;
  const winPct = data.win_rate || 0;
  const lossPct = total ? (data.losing_trades / total) * 100 : 0;

  // Null-safe formatters: a partial /stats payload can leave individual fields
  // undefined even when `stats` itself is non-null, so the defaults above don't
  // cover them. The dashboard deliberately shows zeros (not the em dash) there.
  const fmt = (v) => fx(v, 2, '0.00');
  const pctFmt = (v) => fx(v, 1, '0.0');

  const toggle = (key) => {
    if (typeof onFilterChange !== 'function') return;
    onFilterChange(activeFilter === key ? null : key);
  };

  const Tile = ({ filterKey, label, count, pct, color }) => (
    <button
      type="button"
      className={`kpi-tile ${activeFilter === filterKey ? 'active' : ''}`}
      onClick={() => toggle(filterKey)}
    >
      <div className="kpi-tile-head">
        <span>
          <span className="kpi-tile-label">{label}</span>
          <span className="kpi-tile-count" style={{ color }}>{count}</span>
        </span>
        <span className="kpi-tile-pct">{pctFmt(pct)}%</span>
      </div>
      <div className="kpi-bar">
        <div className="kpi-bar-fill" style={{ width: `${Math.min(100, pct)}%`, background: color }} />
      </div>
    </button>
  );

  const pnlPositive = data.total_pnl >= 0;
  const pnlColor = pnlPositive ? 'var(--success)' : 'var(--danger)';

  return (
    <div className="stats-header">
      <div className="chart-area">
        <EquityCurve />
      </div>

      <div className="kpi-tile-grid">
        <Tile filterKey="wins" label="Wins" count={data.winning_trades} pct={winPct} color="var(--success)" />
        <Tile filterKey="open" label="Open" count={openCount} pct={openPct} color="var(--accent-blue)" />
        <Tile filterKey="losses" label="Losses" count={data.losing_trades} pct={lossPct} color="var(--danger)" />
        <Tile filterKey="wash" label="Wash" count={washCount} pct={washPct} color="var(--text-muted)" />
      </div>

      <div className="avg-stack">
        <div className="avg-line">
          <span className="avg-label">Avg W</span>
          <span className="avg-value" style={{ color: 'var(--success)' }}>${fmt(data.avg_win)}</span>
        </div>
        <div className="avg-line">
          <span className="avg-label">Avg L</span>
          <span className="avg-value" style={{ color: 'var(--danger)' }}>−${fmt(data.avg_loss)}</span>
        </div>
      </div>

      <div className="pnl-block">
        <span className="pnl-label">PnL</span>
        <span className="pnl-value" style={{ color: pnlColor }}>
          {pnlPositive ? '' : '−'}${fmt(Math.abs(Number(data.total_pnl) || 0))}
        </span>
        <span className="pnl-trend" style={{ color: pnlColor }}>
          {pnlPositive ? '↗' : '↘'} {total > 0 ? `${data.total_trades} trades` : 'no trades yet'}
        </span>
      </div>
    </div>
  );
};

export default DashboardStats;
