import React from 'react';
import { TagRow } from './SetupTags';
import { ScoreBreakdownPills } from './ScoreBreakdown';
import ScreenerMiniChart from './ScreenerMiniChart';

const getTierColor = (tier) => {
  switch (tier) {
    case 'S': return '#ff9f43';
    case 'A': return '#bb86fc';
    case 'B': return '#58a6ff';
    case 'C': return '#3fb950';
    default: return '#8b949e';
  }
};

const distanceToTriggerPct = (data) => {
  if (!data?.trigger || !data?.price) return null;
  return ((data.trigger - data.price) / data.price) * 100;
};

const formatMoney = (value) =>
  Number.isFinite(Number(value)) ? `$${Number(value).toFixed(2)}` : '-';

const EarningsChip = ({ info }) => {
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
        padding: '2px 7px',
        borderRadius: '999px',
        fontSize: '10px',
        fontWeight: 700,
        background: tone.bg,
        color: tone.fg,
        fontFamily: "'JetBrains Mono', monospace",
      }}
    >
      ER {days}d
    </span>
  );
};

const WatchlistStar = ({ active, onToggle }) => (
  <button
    onClick={(event) => { event.stopPropagation(); onToggle(); }}
    title={active ? 'Remove from watchlist' : 'Save to watchlist'}
    style={{
      pointerEvents: 'auto',
      background: 'rgba(255,255,255,0.03)',
      border: '1px solid var(--border-color)',
      borderRadius: '6px',
      width: '28px',
      height: '28px',
      cursor: 'pointer',
      fontSize: '15px',
      lineHeight: 1,
      color: active ? '#e3b341' : '#6b6b7a',
      transition: 'color 0.15s, transform 0.15s, border-color 0.15s',
      fontFamily: 'inherit',
    }}
    onMouseEnter={(event) => { event.currentTarget.style.transform = 'scale(1.06)'; }}
    onMouseLeave={(event) => { event.currentTarget.style.transform = 'scale(1)'; }}
  >
    {active ? '★' : '☆'}
  </button>
);

const InfoChip = ({ label, value, tone = 'neutral', title }) => {
  const colors = {
    neutral: { bg: 'rgba(255,255,255,0.04)', fg: 'var(--text-main)', border: 'var(--border-color)' },
    trigger: { bg: 'rgba(61,211,122,0.12)', fg: 'var(--success)', border: 'rgba(61,211,122,0.28)' },
    warning: { bg: 'rgba(240,190,60,0.12)', fg: 'var(--warning)', border: 'rgba(240,190,60,0.28)' },
  };
  const color = colors[tone] || colors.neutral;

  return (
    <span
      title={title}
      style={{
        display: 'inline-flex',
        flexDirection: 'column',
        gap: '2px',
        minWidth: '82px',
        padding: '6px 9px',
        borderRadius: '7px',
        border: `1px solid ${color.border}`,
        background: color.bg,
      }}
    >
      <span style={{ color: 'var(--text-muted)', fontSize: '9px', fontWeight: 700, textTransform: 'uppercase' }}>{label}</span>
      <span style={{ color: color.fg, fontSize: '12px', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
    </span>
  );
};

const ScreenerCard = React.memo(({ ticker, data, earnings, watchlisted, onToggleWatchlist, onClick }) => {
  const triggerPct = distanceToTriggerPct(data);
  const triggerTone = triggerPct != null && triggerPct <= 0.5 ? 'warning' : 'trigger';

  return (
    <div
      onClick={() => onClick(ticker)}
      style={{
        background: 'linear-gradient(180deg, rgba(255,255,255,0.025), rgba(255,255,255,0)), var(--bg-panel)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        minHeight: '406px',
        cursor: 'pointer',
        boxShadow: '0 10px 26px -22px rgba(91,138,255,0.65)',
        transition: 'border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease',
      }}
      onMouseEnter={(event) => {
        event.currentTarget.style.borderColor = 'rgba(91,138,255,0.68)';
        event.currentTarget.style.transform = 'translateY(-2px)';
        event.currentTarget.style.boxShadow = '0 18px 34px -24px rgba(91,138,255,0.95)';
      }}
      onMouseLeave={(event) => {
        event.currentTarget.style.borderColor = 'var(--border-color)';
        event.currentTarget.style.transform = 'translateY(0)';
        event.currentTarget.style.boxShadow = '0 10px 26px -22px rgba(91,138,255,0.65)';
      }}
    >
      <div style={{ padding: '15px 16px 12px', borderBottom: '1px solid rgba(255,255,255,0.055)', display: 'flex', justifyContent: 'space-between', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '9px', minWidth: 0 }}>
          <WatchlistStar active={watchlisted} onToggle={() => onToggleWatchlist(ticker)} />
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 800, fontSize: '19px', color: getTierColor(data.tier), lineHeight: 1.1 }}>{ticker}</div>
            <div style={{ color: 'var(--text-muted)', fontSize: '11px', marginTop: '4px' }}>{data.setup}</div>
          </div>
        </div>
        <div className="screener-card-score-meta">
          <div style={{ fontSize: '11px', color: 'var(--text-main)', display: 'flex', gap: '7px', alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            <EarningsChip info={earnings} />
            <span style={{ padding: '3px 8px', borderRadius: '999px', background: 'rgba(255,255,255,0.055)', fontWeight: 700 }}>{data.tier} TIER</span>
            <span style={{ fontWeight: 700 }}>Score {data.score}</span>
          </div>
          <ScoreBreakdownPills subScores={data.sub_scores} />
        </div>
      </div>

      <div style={{ flex: 1, minHeight: '250px', display: 'flex' }}>
        <ScreenerMiniChart ticker={ticker} data={data} />
      </div>

      <div style={{ padding: '12px 14px', background: 'rgba(26,29,38,0.84)', borderTop: '1px solid rgba(255,255,255,0.055)', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        <InfoChip label="To Trigger" value={triggerPct == null ? '-' : `${triggerPct.toFixed(1)}%`} tone={triggerTone} title={`Distance from current price to LPS high trigger (${formatMoney(data.trigger)})`} />
        <InfoChip label="Price" value={formatMoney(data.price)} />
        <InfoChip label="Base" value={`${data.base_len}d`} />
      </div>

      <TagRow
        subScores={data.sub_scores}
        flags={{
          phaseDInner: data.phase_d_inner,
          rTouchVolZ: data.r_touch_vol_z,
          sTouchVolZ: data.s_touch_vol_z,
        }}
        style={{ padding: '8px 12px 10px', background: 'var(--bg-main)', borderTop: '1px solid var(--border-color)' }}
      />
    </div>
  );
});

export default ScreenerCard;
