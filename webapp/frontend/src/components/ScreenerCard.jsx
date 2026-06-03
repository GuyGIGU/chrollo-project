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

  // Quieted to a single restrained state; only imminent earnings (<=3d) keeps a
  // caution tint, since that's the case actually worth catching the eye.
  const tone = days <= 3
    ? { bg: 'var(--warning-bg)', fg: 'var(--warning)' }
    : { bg: 'rgba(255,255,255,0.05)', fg: 'var(--text-muted)' };

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
        fontSize: 12,
        height: 22,
        lineHeight: 1,
        pointerEvents: 'auto',
        width: 22,
      }}
    >
      {active ? '★' : '☆'}
    </button>
  );
}

// "Considered" marker — records that you actually saw and weighed this setup
// (engaged with it), NOT that you rejected it. So it reads as a neutral
// check-off, never a stop sign.
function PassButton({ active, onToggle }) {
  return (
    <button
      onClick={(event) => {
        event.stopPropagation();
        onToggle();
      }}
      title={active ? 'Considered — you saw & weighed this setup (click to unmark)' : 'Mark as considered (you saw & weighed this setup)'}
      style={{
        background: active ? 'rgba(63,185,80,0.16)' : 'transparent',
        border: '1px solid var(--border-color)',
        borderRadius: 6,
        color: active ? '#3fb950' : '#6b6b7a',
        cursor: 'pointer',
        fontFamily: 'inherit',
        fontSize: 12,
        height: 22,
        lineHeight: 1,
        pointerEvents: 'auto',
        width: 22,
      }}
    >
      {active ? '☑' : '☐'}
    </button>
  );
}

// Small rank badge beside the ticker: reinforces tier without spending more
// color than the ticker hue already does (subtle tinted border, no fill).
const tierBadgeStyle = (tier) => ({
  alignItems: 'center',
  border: `1px solid ${tierColor(tier)}55`,
  borderRadius: 4,
  color: tierColor(tier),
  display: 'inline-flex',
  flexShrink: 0,
  fontSize: 9,
  fontWeight: 800,
  height: 15,
  justifyContent: 'center',
  lineHeight: 1,
  minWidth: 15,
  padding: '0 3px',
});

// Three-zone header: a quiet utility rail (saved/considered), an identity block
// led by the ticker, and a verdict block where the SCORE is the hero figure the
// eye lands on first. Setup label, earnings, and sub-scores recede beneath their
// leaders so the card reads as "rank + score" at a glance during triage.
function CardHeader({ data, earnings, onTogglePassed, onToggleWatchlist, passed, ticker, watchlisted }) {
  return (
    <div
      style={{
        alignItems: 'stretch',
        background: 'rgba(20, 23, 33, 0.98)',
        borderBottom: '1px solid rgba(255,255,255,0.055)',
        display: 'flex',
        gap: 8,
        justifyContent: 'space-between',
        minHeight: 34,
        overflow: 'hidden',
        padding: '6px 8px',
        pointerEvents: 'auto',
      }}
    >
      {/* Utility rail — saved/considered toggles stay quiet on the far left */}
      <div style={{ alignItems: 'center', display: 'flex', flexDirection: 'column', gap: 3 }}>
        <WatchlistButton active={watchlisted} onToggle={() => onToggleWatchlist(ticker)} />
        <PassButton active={passed} onToggle={() => onTogglePassed(ticker)} />
      </div>

      {/* Identity — ticker leads; setup + earnings recede onto a quiet sub-line */}
      <div style={{ alignSelf: 'center', display: 'flex', flex: 1, flexDirection: 'column', gap: 3, minWidth: 0 }}>
        <div style={{ alignItems: 'center', display: 'flex', gap: 6, minWidth: 0 }}>
          <span style={{ color: tierColor(data.tier), fontSize: 18, fontWeight: 850, letterSpacing: '-0.01em', lineHeight: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {ticker}
          </span>
          <span style={tierBadgeStyle(data.tier)}>{data.tier}</span>
        </div>
        <div style={{ alignItems: 'center', display: 'flex', gap: 6, minWidth: 0 }}>
          <span style={{ color: 'var(--text-faint)', fontSize: 10, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {data.setup}
          </span>
          <EarningsChip info={earnings} />
        </div>
      </div>

      {/* Verdict — the score is the figure the eye should land on first */}
      <div style={{ alignItems: 'flex-end', display: 'flex', flexDirection: 'column', gap: 4, justifyContent: 'center' }}>
        <div style={{ alignItems: 'baseline', display: 'flex', gap: 4 }}>
          <span style={{ color: 'var(--text-faint)', fontSize: 9, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
            Score
          </span>
          <span style={{ color: 'var(--text-main)', fontSize: 22, fontWeight: 800, fontVariantNumeric: 'tabular-nums', lineHeight: 1 }}>
            {data.score}
          </span>
        </div>
        <ScoreBreakdownPills subScores={data.sub_scores} className="score-breakdown-compact" />
      </div>
    </div>
  );
}

const ScreenerCard = React.memo(({ ticker, data, earnings, watchlisted, onToggleWatchlist, passed, onTogglePassed, onClick }) => (
  <div
    className="screener-card"
    role="button"
    tabIndex={0}
    aria-label={`Open ${ticker} chart — ${data.setup}, tier ${data.tier}, score ${data.score}`}
    onClick={() => onClick(ticker)}
    onKeyDown={(event) => {
      // Make the card a real keyboard target: Enter/Space open it, matching the
      // click. preventDefault stops Space from scrolling the page.
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        onClick(ticker);
      }
    }}
    style={{
      background: 'var(--bg-panel)',
      border: '1px solid var(--border-color)',
      borderRadius: 'var(--radius-sm)',
      cursor: 'pointer',
      display: 'flex',
      flexDirection: 'column',
      // Passed cards are dimmed so the grid reads as "what's left to review".
      opacity: passed ? 0.5 : 1,
      overflow: 'hidden',
      transition: 'border-color 0.16s ease, background 0.16s ease, opacity 0.16s ease',
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
      onTogglePassed={onTogglePassed}
      onToggleWatchlist={onToggleWatchlist}
      passed={passed}
      ticker={ticker}
      watchlisted={watchlisted}
    />
    <div style={{ display: 'flex', height: 'clamp(130px, 7vw, 148px)', minHeight: 130, position: 'relative' }}>
      <ScreenerMiniChart ticker={ticker} data={data} />
    </div>
    <TagRow
      subScores={data.sub_scores}
      flags={{
        phaseDInner: data.phase_d_inner,
        rTouchVolZ: data.r_touch_vol_z,
        sTouchVolZ: data.s_touch_vol_z,
      }}
      compact
      maxTags="auto"
      style={{
        background: 'var(--bg-main)',
        borderTop: '1px solid var(--border-color)',
        flexWrap: 'nowrap',
        height: 28,
        overflow: 'hidden',
        padding: '4px 8px',
      }}
    />
  </div>
));

export default ScreenerCard;
