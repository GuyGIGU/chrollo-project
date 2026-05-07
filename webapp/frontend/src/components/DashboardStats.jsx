import React from 'react';
import EquityCurve from './EquityCurve';

const RING_R = 18;
const RING_C = 2 * Math.PI * RING_R;

function RingClock({ pct, color, label, active, muted }) {
  const clamped = Math.max(0, Math.min(100, pct || 0));
  const dash = (clamped / 100) * RING_C;
  const stroke = muted ? 'var(--border-color)' : color;
  const textColor = muted ? 'var(--text-muted)' : color;
  return (
    <div
      className="kpi-circ"
      style={{
        position: 'relative',
        width: 44,
        height: 44,
        border: 'none',
        background: 'transparent',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        boxShadow: active ? `0 0 0 2px ${stroke}, 0 0 10px ${stroke}` : 'none',
        borderRadius: '50%',
        transition: 'box-shadow 120ms ease',
      }}
      aria-label={label}
    >
      <svg width="44" height="44" viewBox="0 0 44 44" style={{ transform: 'rotate(-90deg)' }}>
        <circle cx="22" cy="22" r={RING_R} fill="none" stroke="var(--border-color)" strokeWidth="3" opacity="0.5" />
        <circle
          cx="22"
          cy="22"
          r={RING_R}
          fill="none"
          stroke={stroke}
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${RING_C}`}
          style={{ transition: 'stroke-dasharray 250ms ease' }}
        />
      </svg>
      <span style={{ position: 'absolute', fontSize: 10, fontWeight: 600, color: textColor }}>
        {Math.round(clamped)}%
      </span>
    </div>
  );
}

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
  const lossPct = data.win_rate > 0 || data.losing_trades > 0 ? 100 - data.win_rate : 0;

  const toggle = (key) => {
    if (typeof onFilterChange !== 'function') return;
    onFilterChange(activeFilter === key ? null : key);
  };

  const filterBtnStyle = (key) => ({
    display: 'flex',
    alignItems: 'center',
    gap: '0.6rem',
    background: activeFilter === key ? 'var(--bg-hover)' : 'transparent',
    border: 'none',
    padding: '0.3rem 0.5rem',
    borderRadius: 'var(--radius-sm, 6px)',
    cursor: 'pointer',
    color: 'inherit',
    textAlign: 'left',
  });

  return (
    <div className="stats-header">
      <div
        className="chart-area"
        style={{
          background: 'linear-gradient(180deg, var(--bg-hover) 0%, var(--bg-panel) 100%)',
          padding: '0.5rem 0.75rem',
          position: 'relative',
        }}
      >
        <EquityCurve />
      </div>

      <div className="kpi-row">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
          <button type="button" onClick={() => toggle('wins')} style={filterBtnStyle('wins')}>
            <span style={{ color: 'var(--text-muted)', width: '45px' }}>WINS</span>
            <span style={{ color: 'var(--success)', fontWeight: 'bold', width: '20px' }}>{data.winning_trades}</span>
            <RingClock pct={winPct} color="var(--success)" label={`wins ${winPct}%`} active={activeFilter === 'wins'} />
          </button>
          <button type="button" onClick={() => toggle('losses')} style={filterBtnStyle('losses')}>
            <span style={{ color: 'var(--text-muted)', width: '45px' }}>LOSSES</span>
            <span style={{ color: 'var(--danger)', fontWeight: 'bold', width: '20px' }}>{data.losing_trades}</span>
            <RingClock pct={lossPct} color="var(--danger)" label={`losses ${lossPct}%`} active={activeFilter === 'losses'} />
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
          <button type="button" onClick={() => toggle('open')} style={filterBtnStyle('open')}>
            <span style={{ color: 'var(--text-muted)', width: '40px' }}>OPEN</span>
            <span style={{ color: 'var(--accent-blue)', fontWeight: 'bold', width: '20px' }}>{openCount}</span>
            <RingClock pct={openPct} color="var(--accent-blue)" label={`open ${openPct}%`} active={activeFilter === 'open'} muted={openCount === 0} />
          </button>
          <button type="button" onClick={() => toggle('wash')} style={filterBtnStyle('wash')}>
            <span style={{ color: 'var(--text-muted)', width: '40px' }}>WASH</span>
            <span style={{ color: 'var(--text-muted)', fontWeight: 'bold', width: '20px' }}>{washCount}</span>
            <RingClock pct={washPct} color="var(--text-muted)" label={`wash ${washPct}%`} active={activeFilter === 'wash'} muted={washCount === 0} />
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
          <div className="kpi-block">
            <span style={{ color: 'var(--text-muted)', width: '40px' }}>AVG W</span>
            <span style={{ color: 'var(--success)', fontWeight: 'bold', width: '40px' }}>${data.avg_win.toFixed(2)}</span>
          </div>
          <div className="kpi-block">
            <span style={{ color: 'var(--text-muted)', width: '40px' }}>AVG L</span>
            <span style={{ color: 'var(--danger)', fontWeight: 'bold', width: '40px' }}>-${data.avg_loss.toFixed(2)}</span>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginLeft: '1rem' }}>
          <span style={{ color: 'var(--text-muted)', fontSize: '10px', marginBottom: '0.5rem' }}>PnL</span>
          <div
            style={{
              background: data.total_pnl >= 0 ? 'var(--success-bg)' : 'var(--danger-bg)',
              color: data.total_pnl >= 0 ? 'var(--success)' : 'var(--danger)',
              padding: '0.4rem 1.2rem',
              borderRadius: 'var(--radius-pill)',
              fontWeight: 'bold',
              border: `1px solid ${data.total_pnl >= 0 ? 'var(--success)' : 'var(--danger)'}`,
            }}
          >
            ${data.total_pnl.toFixed(2)}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardStats;
