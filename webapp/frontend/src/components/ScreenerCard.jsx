import React from 'react';
import { TagRow } from './SetupTags';
import { ScoreBreakdownPills } from './ScoreBreakdown';
import ScreenerMiniChart from './ScreenerMiniChart';

const tierColor = (tier) => {
  switch (tier) {
    case 'S': return '#ff9f43';
    case 'A': return '#bb86fc';
    case 'B': return '#58a6ff';
    case 'C': return '#3fb950';
    default: return '#8b949e';
  }
};

function EarningsChip({ info }) {
  if (!info || info.days_until == null) return null;
  const days = info.days_until;
  if (days < 0 || days > 14) return null;

  const tone = days <= 3
    ? { bg: 'rgba(242,103,112,0.18)', fg: '#ff8c8c' }
    : days <= 7
      ? { bg: 'rgba(240,190,60,0.16)', fg: '#f0be3c' }
      : { bg: 'rgba(88,166,255,0.15)', fg: '#58a6ff' };

  return (
    <span
      title={`Earnings in ${days} day${days === 1 ? '' : 's'} (${info.date})`}
      style={{
        background: tone.bg,
        borderRadius: 6,
        color: tone.fg,
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10,
        fontWeight: 700,
        padding: '1px 6px',
      }}
    >
      ER {days}d
    </span>
  );
}

function WatchlistButton({ active, onToggle }) {
  return (
    <button
      onClick={(event) => {
        event.stopPropagation();
        onToggle();
      }}
      title={active ? 'Remove from watchlist' : 'Save to watchlist'}
      style={{
        background: 'transparent',
        border: '1px solid var(--border-color)',
        borderRadius: 6,
        color: active ? '#e3b341' : '#6b6b7a',
        cursor: 'pointer',
        fontFamily: 'inherit',
        fontSize: 14,
        height: 26,
        lineHeight: 1,
        pointerEvents: 'auto',
        width: 26,
      }}
    >
      {active ? '*' : '+'}
    </button>
  );
}

function CardHeader({ data, earnings, onToggleWatchlist, ticker, watchlisted }) {
  return (
    <div style={{
      alignItems: 'center',
      borderBottom: '1px solid rgba(255,255,255,0.055)',
      display: 'flex',
      gap: 12,
      height: 56,
      justifyContent: 'space-between',
      overflow: 'hidden',
      padding: '10px 12px 8px',
    }}>
      <div style={{ alignItems: 'center', display: 'flex', gap: 9, minWidth: 0 }}>
        <WatchlistButton active={watchlisted} onToggle={() => onToggleWatchlist(ticker)} />
        <div style={{ minWidth: 0 }}>
          <div style={{ alignItems: 'center', display: 'flex', gap: 8 }}>
            <span style={{ color: tierColor(data.tier), fontSize: 18, fontWeight: 850, lineHeight: 1.1 }}>
              {ticker}
            </span>
            <span style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 800 }}>{data.tier}</span>
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {data.setup}
          </div>
        </div>
      </div>
      <div className="screener-card-score-meta">
        <div style={{ alignItems: 'center', color: 'var(--text-main)', display: 'flex', flexWrap: 'wrap', fontSize: 11, gap: 7, justifyContent: 'flex-end' }}>
          <EarningsChip info={earnings} />
          <span style={{ fontWeight: 700 }}>Score {data.score}</span>
        </div>
        <ScoreBreakdownPills subScores={data.sub_scores} className="score-breakdown-compact" />
      </div>
    </div>
  );
}

const ScreenerCard = React.memo(({ ticker, data, earnings, watchlisted, onToggleWatchlist, onClick }) => (
  <div
    onClick={() => onClick(ticker)}
    style={{
      background: 'var(--bg-panel)',
      border: '1px solid var(--border-color)',
      borderRadius: 8,
      cursor: 'pointer',
      display: 'flex',
      flexDirection: 'column',
      minHeight: 276,
      overflow: 'hidden',
      transition: 'border-color 0.16s ease, background 0.16s ease',
    }}
    onMouseEnter={(event) => {
      event.currentTarget.style.borderColor = 'rgba(91,138,255,0.58)';
      event.currentTarget.style.background = '#242837';
    }}
    onMouseLeave={(event) => {
      event.currentTarget.style.borderColor = 'var(--border-color)';
      event.currentTarget.style.background = 'var(--bg-panel)';
    }}
  >
    <CardHeader
      data={data}
      earnings={earnings}
      onToggleWatchlist={onToggleWatchlist}
      ticker={ticker}
      watchlisted={watchlisted}
    />
    <div style={{ display: 'flex', height: 172, minHeight: 172 }}>
      <ScreenerMiniChart ticker={ticker} data={data} />
    </div>
    <TagRow
      subScores={data.sub_scores}
      flags={{
        phaseDInner: data.phase_d_inner,
        rTouchVolZ: data.r_touch_vol_z,
        sTouchVolZ: data.s_touch_vol_z,
      }}
      style={{
        background: 'var(--bg-main)',
        borderTop: '1px solid var(--border-color)',
        height: 46,
        overflow: 'hidden',
        padding: '7px 12px 8px',
      }}
    />
  </div>
));

export default ScreenerCard;
