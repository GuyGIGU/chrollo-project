import React from 'react';
import { TagRow } from './SetupTags';
import ScreenerMiniChart from '../charts/ScreenerMiniChart';
import { explainTip } from '../formatting/tooltipText';
import { healthStateMeta } from './healthStateData';
import { tierColor, signColor } from '../presentation/theme';
import { fx, fmtSignedPctFrac } from '../formatting/format';
import { dailyChangeFrac, asOfDate, htfStateLabel, htfTrendArrow } from './screenerCardData';

export function WatchlistButton({ active, onToggle }) {
  return (
    <button
      onClick={(event) => {
        event.stopPropagation();
        onToggle();
      }}
      title={active ? 'Remove from watchlist' : 'Save to watchlist'}
      style={{
        background: 'rgba(20,23,33,0.7)',
        border: '1px solid var(--border-color)',
        borderRadius: 5,
        color: active ? 'var(--accent-yellow)' : 'var(--text-faint)',
        cursor: 'pointer',
        fontFamily: 'inherit',
        fontSize: 11,
        height: 20,
        lineHeight: 1,
        pointerEvents: 'auto',
        width: 20,
      }}
    >
      {active ? '★' : '☆'}
    </button>
  );
}

// LIKE — "this is the kind of setup I want more of" (operator 2026-09-02),
// replacing the old neutral "considered" check-off on this surface. It is a
// PREFERENCE signal about the engine's own fires, gathered so the good ones can
// eventually be singled out of a scan; the "saw & skipped" negative it is paired
// with lives on the archive table, and the two are one mutually-exclusive row
// server-side. Nothing in the engine reads a like, and nothing may until it has
// been measured against the archive (house rule: new signals enter measure-first).
//
// It reads as approval, not as a stop sign: the filled heart takes the gold the
// app already spends on the operator's own marks, never a tier hue.
function LikeButton({ active, onToggle }) {
  return (
    <button
      onClick={(event) => {
        event.stopPropagation();
        onToggle();
      }}
      aria-pressed={active}
      title={active ? 'Liked — the kind of setup you want more of (click to unlike)' : 'Like this setup — the kind you want more of'}
      style={{
        background: active ? 'rgba(212,175,55,0.16)' : 'rgba(20,23,33,0.7)',
        border: `1px solid ${active ? 'var(--accent-yellow)' : 'var(--border-color)'}`,
        borderRadius: 5,
        color: active ? 'var(--accent-yellow)' : '#6b6b7a',
        cursor: 'pointer',
        fontFamily: 'inherit',
        fontSize: 11,
        height: 20,
        lineHeight: 1,
        pointerEvents: 'auto',
        width: 20,
      }}
    >
      {active ? '♥' : '♡'}
    </button>
  );
}

// Small rank badge beside the ticker: reinforces tier without spending more
// color than the ticker hue already does (subtle tinted border, no fill).
const tierBadgeStyle = (tier) => ({
  alignItems: 'center',
  border: `1px solid ${tierColor(tier)}55`,
  borderRadius: 'var(--radius-xs)',
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

// One timeframe's read: trend arrow (color = up/down/neutral), the structural
// state (re-accum / consol+phase / stage-2 / —), and a nesting mark when the
// daily base sits inside this timeframe's box. Re-accumulation is the premium
// case, so it takes the categorical gold. Rendered compact on the card's meta row.
function TimeframeCell({ tf, stage2, trendState, inConsol, phase, reaccum, nested }) {
  const trend = htfTrendArrow(trendState);
  const { label: state, tone: stateCol } = htfStateLabel({ stage2, trendState, inConsol, phase, reaccum });
  const tfName = tf === 'W' ? 'Weekly' : 'Monthly';
  const status = [
    `trend ${trendState || 'unknown'}`,
    inConsol ? `worked box phase ${phase || '?'}` : 'no worked box',
    reaccum ? 're-accumulation: established uptrend plus consolidation' : null,
    nested ? 'daily base nests inside this higher-timeframe box' : null,
  ].filter(Boolean).join('; ');
  const title = explainTip({
    what: `${tfName} context for the same setup engine: ${status}.`,
    why: 'Higher-timeframe agreement helps separate a small daily pattern from a setup aligned with a larger established uptrend or Wyckoff-style trend pause.',
    use: 'Give more weight to daily setups that are also supported by weekly or monthly re-accumulation; be stricter when context is weak or missing.',
  });
  return (
    <div title={title} style={{ alignItems: 'center', display: 'flex', gap: 5, minWidth: 0 }}>
      <span style={{ color: 'var(--text-faint)', fontSize: 10, fontWeight: 700, letterSpacing: '0.08em' }}>{tf}</span>
      <span style={{ color: trend.col, fontSize: 13, lineHeight: 1 }}>{trend.sym}</span>
      <span style={{ color: stateCol, fontSize: 11, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{state}</span>
      {nested ? <span style={{ color: 'var(--accent-yellow)', fontSize: 13, lineHeight: 1 }}>⊂</span> : null}
    </div>
  );
}

const monoFaint = { color: 'var(--text-faint)', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, whiteSpace: 'nowrap' };

// Minimal Finviz charts-view header, ONE row since 2026-10-02 — the operator
// circled the old two-row header as space the chart should get ("increasing the
// real state each setup gets in the mini chart cards"). Stock + tier + sector
// ETF, then the weekly / monthly read, then — pushed right — the as-of date, the
// live price and its daily % change, and the two toggles. The W/M group is the
// ONE part that gives way: on a narrow (480px) card its state words ellipsize so
// the row never wraps or overflows; the full read stays in each cell's tooltip.
// The shell (.screener-card-head, 30px) is shared with the health card and the
// Watchlist's clean card, so every card kind's chart starts at the same height.
// Score, setup name, and the next-earnings date live in the click-through detail
// lens, keeping the card face to the chart itself.
function CardHeader({ data, ticker, watchlisted, onToggleWatchlist, liked, onToggleLike }) {
  const changePct = dailyChangeFrac(data.candles);
  const hasHtf = data.htf_w_trend_state != null || data.htf_m_trend_state != null;

  return (
    <div className="screener-card-head" style={{ pointerEvents: 'auto' }}>
      <span style={{ color: tierColor(data.tier), flexShrink: 0, fontSize: 17, fontWeight: 850, letterSpacing: '-0.01em', lineHeight: 1, whiteSpace: 'nowrap' }}>
        {ticker}
      </span>
      <span style={tierBadgeStyle(data.tier)}>{data.tier}</span>
      {data.sector_etf ? (
        <span style={{ alignItems: 'center', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-xs)', color: 'var(--text-muted)', display: 'inline-flex', flexShrink: 0, fontFamily: "'JetBrains Mono', monospace", fontSize: 11, height: 15, lineHeight: 1, padding: '0 4px' }}>
          {data.sector_etf}
        </span>
      ) : null}

      {/* The weekly / monthly read — shrinks first (minWidth 0 + overflow) */}
      <div style={{ alignItems: 'center', display: 'flex', flex: '0 1 auto', gap: 8, marginLeft: 3, minWidth: 0, overflow: 'hidden' }}>
        {hasHtf ? (
          <>
            <TimeframeCell tf="W" stage2={data.htf_w_stage2} trendState={data.htf_w_trend_state} inConsol={data.htf_w_in_consol} phase={data.htf_w_phase} reaccum={data.htf_w_reaccum} nested={data.htf_w_daily_nested} />
            <span style={{ alignSelf: 'stretch', background: 'var(--border-color)', flexShrink: 0, margin: '2px 0', width: 1 }} />
            <TimeframeCell tf="M" stage2={data.htf_m_stage2} trendState={data.htf_m_trend_state} inConsol={data.htf_m_in_consol} phase={data.htf_m_phase} reaccum={data.htf_m_reaccum} nested={data.htf_m_daily_nested} />
          </>
        ) : (
          <span style={{ color: 'var(--text-faint)', fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>Daily setup</span>
        )}
      </div>

      <span style={{ ...monoFaint, flexShrink: 0, marginLeft: 'auto' }}>
        {asOfDate(data.candles)}
      </span>
      <span style={{ alignItems: 'baseline', display: 'flex', flexShrink: 0, gap: 6 }}>
        <span style={{ color: 'var(--text-main)', fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700, whiteSpace: 'nowrap' }}>
          ${fx(data.price, 2)}
        </span>
        {changePct != null && (
          <span style={{ color: signColor(changePct) || 'var(--text-muted)', fontFamily: "'JetBrains Mono', monospace", fontSize: 12, fontWeight: 700, whiteSpace: 'nowrap' }}>
            {fmtSignedPctFrac(changePct, 1)}
          </span>
        )}
      </span>
      <span style={{ display: 'flex', flexShrink: 0, gap: 4, marginLeft: 2 }}>
        <WatchlistButton active={watchlisted} onToggle={() => onToggleWatchlist(ticker)} />
        <LikeButton active={liked} onToggle={() => onToggleLike(ticker)} />
      </span>
    </div>
  );
}

// The chart well, locked to the card's WIDTH (2026-10-02): a 1.9:1 aspect from
// index.css, so the card draws a setup in the same proportions on every monitor
// instead of taking its height from the viewport. Shared by both card kinds.
const chartWellStyle = {
  aspectRatio: 'var(--card-chart-aspect)',
  display: 'flex',
  flexShrink: 0,
  minHeight: 'var(--card-chart-min-h)',
  position: 'relative',
};

// Quiet full-width drill affordance, only on ETF-universe cards (when onDrilldown
// is passed). Visually separate from the card's open-the-chart click, and it
// stops propagation so the two never fire together.
const drillButtonStyle = {
  background: 'var(--bg-main)',
  border: 'none',
  borderTop: '1px solid var(--border-color)',
  color: 'var(--text-muted)',
  cursor: 'pointer',
  fontFamily: "'JetBrains Mono', monospace",
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: '0.04em',
  padding: '7px 8px',
  textAlign: 'left',
  width: '100%',
};

const FiringCard = React.memo(({ ticker, data, watchlisted, onToggleWatchlist, liked, onToggleLike, onClick, onDrilldown }) => (
  <div
    className="screener-card"
    role="button"
    tabIndex={0}
    aria-label={`Open ${ticker} chart, tier ${data.tier}. Press W to ${watchlisted ? 'remove from' : 'save to'} watchlist, L to ${liked ? 'unlike' : 'like'}.`}
    onClick={() => onClick(ticker)}
    onKeyDown={(event) => {
      // Only act on keys aimed at the card itself, not ones bubbling up from the
      // inner toggle buttons (otherwise Enter/Space on a focused toggle would
      // also open the card). Enter/Space open it; W/L are power-user toggles that
      // keep the per-card engagement a like depends on — a deliberate
      // alternative to mass-marking a whole page at once.
      if (event.target !== event.currentTarget) return;
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        onClick(ticker);
      } else if (event.key === 'w' || event.key === 'W') {
        event.preventDefault();
        onToggleWatchlist(ticker);
      } else if (event.key === 'l' || event.key === 'L') {
        event.preventDefault();
        onToggleLike(ticker);
      }
    }}
    style={{
      background: 'var(--bg-panel)',
      border: '1px solid var(--border-color)',
      borderRadius: 'var(--radius-sm)',
      cursor: 'pointer',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      transition: 'border-color 0.16s ease, background 0.16s ease, box-shadow 0.18s ease, transform 0.18s cubic-bezier(0.22, 1, 0.36, 1)',
    }}
    onMouseEnter={(event) => {
      event.currentTarget.style.borderColor = 'rgba(79,207,196,0.65)';
      event.currentTarget.style.background = '#242837';
    }}
    onMouseLeave={(event) => {
      event.currentTarget.style.borderColor = 'var(--border-color)';
      event.currentTarget.style.background = 'var(--bg-panel)';
    }}
  >
    <CardHeader
      data={data}
      liked={liked}
      onToggleLike={onToggleLike}
      onToggleWatchlist={onToggleWatchlist}
      ticker={ticker}
      watchlisted={watchlisted}
    />
    <div className="screener-card-well" style={chartWellStyle}>
      <ScreenerMiniChart ticker={ticker} data={data} />
    </div>
    {/* ONE row of chips (2026-10-02); what does not fit folds into TagRow's +N,
        whose tooltip lists the rest — a chip is shown whole or not at all. */}
    <TagRow
      data={data}
      compact
      maxTags="auto"
      rows={1}
      style={{
        alignContent: 'center',
        background: 'var(--bg-main)',
        borderTop: '1px solid var(--border-color)',
        flexShrink: 0,
        flexWrap: 'wrap',
        height: 28,
        overflow: 'hidden',
        padding: '5px 8px',
      }}
    />
    {onDrilldown && (
      <button
        type="button"
        className="focus-ring"
        title={`Show the US-stocks related to ${ticker}`}
        onClick={(event) => { event.stopPropagation(); onDrilldown(ticker); }}
        style={drillButtonStyle}
        onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--myth)'; }}
        onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)'; }}
      >
        Members →
      </button>
    )}
  </div>
));

// The neutral state chip — the health card's single new protagonist. Loud by
// SIZE / WEIGHT / PLACEMENT (it fills the slot the score used to own), never by
// color: zero hue on state, so the whole board can't read as a red/green signal.
// Decision-point states get a touch more presence; dormant ones recede.
function StateChip({ state }) {
  const meta = healthStateMeta(state);
  return (
    <span
      title={explainTip({
        what: `Position in cycle: ${meta.label.toLowerCase()} — ${meta.blurb}`,
        why: 'This board reads where each member sits in its cycle, not whether to trade it — a market index resting on support is a hint about which stocks to look at next.',
        use: 'Use it as top-down context; drill into the related US stocks for anything actionable.',
      })}
      style={{
        alignSelf: 'center',
        background: meta.decision ? 'var(--bg-elevated)' : 'rgba(255,255,255,0.03)',
        border: `1px solid ${meta.decision ? 'var(--border-strong)' : 'var(--border-color)'}`,
        borderRadius: 'var(--radius-pill)',
        color: meta.decision ? 'var(--text-main)' : 'var(--text-muted)',
        flexShrink: 0,
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 12,
        fontWeight: 700,
        letterSpacing: '0.01em',
        lineHeight: 1.2,
        padding: '2px 10px', // fits the 30px one-row header (was 4px 11px)
        whiteSpace: 'nowrap',
      }}
    >
      {meta.label}
    </span>
  );
}

// The HEALTH variant: a real render branch away from the setup card. It reuses the
// SAME ScreenerMiniChart (so the chart + box overlay can't diverge) but shows NO
// score / tier / setup / trigger / sub-scores / tag row — the ticker is neutral
// (no tier hue: the absence of a ranked color is itself the "context, not a setup"
// tell) and the vacated verdict slot holds one neutral state chip.
const HealthCard = React.memo(({ ticker, data, onDrilldown }) => (
  <div
    className="screener-card"
    aria-label={`${ticker} — ${healthStateMeta(data.state).label}. ${healthStateMeta(data.state).blurb}`}
    style={{
      background: 'var(--bg-panel)',
      border: '1px solid var(--border-color)',
      borderRadius: 'var(--radius-sm)',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      transition: 'border-color 0.16s ease, background 0.16s ease',
    }}
    onMouseEnter={(event) => {
      event.currentTarget.style.borderColor = 'rgba(79,207,196,0.65)';
      event.currentTarget.style.background = '#242837';
    }}
    onMouseLeave={(event) => {
      event.currentTarget.style.borderColor = 'var(--border-color)';
      event.currentTarget.style.background = 'var(--bg-panel)';
    }}
  >
    {/* Header mirrors the firing card's ONE-row shell (2026-10-02) so nothing
        jumps between tabs: ticker and name on one line (the name gives way),
        the state chip in the verdict slot. */}
    <div
      className="screener-card-head"
      style={{ background: 'rgba(20, 23, 33, 0.98)', justifyContent: 'space-between', overflow: 'hidden' }}
    >
      <div style={{ alignItems: 'baseline', display: 'flex', gap: 7, minWidth: 0 }}>
        <span style={{ color: 'var(--text-main)', flexShrink: 0, fontSize: 17, fontWeight: 850, letterSpacing: '-0.01em', lineHeight: 1, whiteSpace: 'nowrap' }}>
          {ticker}
        </span>
        {data.name ? (
          <span title={data.name} style={{ color: 'var(--text-faint)', fontSize: 11, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {data.name}
          </span>
        ) : null}
      </div>
      <StateChip state={data.state} />
    </div>

    <div style={chartWellStyle}>
      <ScreenerMiniChart ticker={ticker} data={data} />
    </div>

    {onDrilldown && (
      <button
        type="button"
        className="focus-ring"
        title={`Show the US stocks related to ${ticker}`}
        onClick={(event) => { event.stopPropagation(); onDrilldown(ticker); }}
        style={drillButtonStyle}
        onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--myth)'; }}
        onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)'; }}
      >
        Members →
      </button>
    )}
  </div>
));

// One entry point, two render branches: the `health` prop routes a member to the
// context-read variant; everything else is the unchanged firing card.
const ScreenerCard = (props) => (props.health ? <HealthCard {...props} /> : <FiringCard {...props} />);

export default ScreenerCard;
