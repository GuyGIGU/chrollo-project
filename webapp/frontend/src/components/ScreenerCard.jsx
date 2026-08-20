import React from 'react';
import { TagRow } from './SetupTags';
import ScreenerMiniChart from './ScreenerMiniChart';
import { explainTip } from './tooltipText';
import { healthStateMeta } from './healthStateData';
import { tierColor, signColor } from '../theme';
import { fx, fmtSignedPctFrac } from '../utils/format';
import { dailyChangeFrac, asOfDate, htfStateLabel, htfTrendArrow } from '../utils/screenerCardData';

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
        background: active ? 'var(--success-bg)' : 'rgba(20,23,33,0.7)',
        border: '1px solid var(--border-color)',
        borderRadius: 5,
        color: active ? 'var(--success)' : '#6b6b7a',
        cursor: 'pointer',
        fontFamily: 'inherit',
        fontSize: 11,
        height: 20,
        lineHeight: 1,
        pointerEvents: 'auto',
        width: 20,
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

// Minimal Finviz charts-view header: the top line is stock + tier + date; the
// meta line is the weekly / monthly trend read (moved up from the old HTF band)
// plus the live price and its daily % change. Score, setup name, and the next-
// earnings date move to the click-through detail lens, keeping the card face to
// the chart itself.
function CardHeader({ data, ticker, watchlisted, onToggleWatchlist, passed, onTogglePassed }) {
  const changePct = dailyChangeFrac(data.candles);
  const hasHtf = data.htf_w_trend_state != null || data.htf_m_trend_state != null;

  return (
    <div
      style={{
        background: 'rgba(20, 23, 33, 0.5)',
        borderBottom: '1px solid rgba(255,255,255,0.055)',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        padding: '9px 10px',
        pointerEvents: 'auto',
        position: 'relative',
      }}
    >
      {/* Utility toggles float in the top-right corner, out of the reading path */}
      <div style={{ display: 'flex', gap: 4, position: 'absolute', right: 9, top: 8 }}>
        <WatchlistButton active={watchlisted} onToggle={() => onToggleWatchlist(ticker)} />
        <PassButton active={passed} onToggle={() => onTogglePassed(ticker)} />
      </div>

      {/* Row 1 — stock + tier + date (date clears the corner toggles) */}
      <div style={{ alignItems: 'center', display: 'flex', gap: 7, minWidth: 0, paddingRight: 52 }}>
        <span style={{ color: tierColor(data.tier), fontSize: 19, fontWeight: 850, letterSpacing: '-0.01em', lineHeight: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {ticker}
        </span>
        <span style={tierBadgeStyle(data.tier)}>{data.tier}</span>
        {data.sector_etf ? (
          <span style={{ alignItems: 'center', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-xs)', color: 'var(--text-muted)', display: 'inline-flex', flexShrink: 0, fontFamily: "'JetBrains Mono', monospace", fontSize: 11, height: 15, lineHeight: 1, padding: '0 4px' }}>
            {data.sector_etf}
          </span>
        ) : null}
        <span style={{ color: 'var(--text-faint)', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, marginLeft: 'auto', whiteSpace: 'nowrap' }}>
          {asOfDate(data.candles)}
        </span>
      </div>

      {/* Row 2 — weekly / monthly read, then price + daily change on the right */}
      <div style={{ alignItems: 'center', display: 'flex', gap: 10, minWidth: 0 }}>
        {hasHtf ? (
          <>
            <TimeframeCell tf="W" stage2={data.htf_w_stage2} trendState={data.htf_w_trend_state} inConsol={data.htf_w_in_consol} phase={data.htf_w_phase} reaccum={data.htf_w_reaccum} nested={data.htf_w_daily_nested} />
            <span style={{ alignSelf: 'stretch', background: 'var(--border-color)', width: 1 }} />
            <TimeframeCell tf="M" stage2={data.htf_m_stage2} trendState={data.htf_m_trend_state} inConsol={data.htf_m_in_consol} phase={data.htf_m_phase} reaccum={data.htf_m_reaccum} nested={data.htf_m_daily_nested} />
          </>
        ) : (
          <span style={{ color: 'var(--text-faint)', fontSize: 11 }}>Daily setup</span>
        )}
        <span style={{ alignItems: 'baseline', display: 'flex', gap: 6, marginLeft: 'auto' }}>
          <span style={{ color: 'var(--text-main)', fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700 }}>
            ${fx(data.price, 2)}
          </span>
          {changePct != null && (
            <span style={{ color: signColor(changePct) || 'var(--text-muted)', fontFamily: "'JetBrains Mono', monospace", fontSize: 12, fontWeight: 700 }}>
              {fmtSignedPctFrac(changePct, 1)}
            </span>
          )}
        </span>
      </div>
    </div>
  );
}

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

const FiringCard = React.memo(({ ticker, data, watchlisted, onToggleWatchlist, passed, onTogglePassed, onClick, onDrilldown }) => (
  <div
    className="screener-card"
    role="button"
    tabIndex={0}
    aria-label={`Open ${ticker} chart, tier ${data.tier}. Press W to ${watchlisted ? 'remove from' : 'save to'} watchlist, C to mark considered.`}
    onClick={() => onClick(ticker)}
    onKeyDown={(event) => {
      // Only act on keys aimed at the card itself, not ones bubbling up from the
      // inner toggle buttons (otherwise Enter/Space on a focused toggle would
      // also open the card). Enter/Space open it; W/C are power-user toggles that
      // keep the per-card engagement the "considered" mark depends on — a
      // deliberate alternative to mass-marking a whole page at once.
      if (event.target !== event.currentTarget) return;
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        onClick(ticker);
      } else if (event.key === 'w' || event.key === 'W') {
        event.preventDefault();
        onToggleWatchlist(ticker);
      } else if (event.key === 'c' || event.key === 'C') {
        event.preventDefault();
        onTogglePassed(ticker);
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
      onTogglePassed={onTogglePassed}
      onToggleWatchlist={onToggleWatchlist}
      passed={passed}
      ticker={ticker}
      watchlisted={watchlisted}
    />
    <div className="screener-card-well" style={{ display: 'flex', height: 'clamp(180px, 11vw, 240px)', minHeight: 180, position: 'relative' }}>
      <ScreenerMiniChart ticker={ticker} data={data} />
    </div>
    <TagRow
      data={data}
      compact
      maxTags="auto"
      rows={2}
      style={{
        alignContent: 'flex-start',
        background: 'var(--bg-main)',
        borderTop: '1px solid var(--border-color)',
        flexWrap: 'wrap',
        height: 52,
        overflow: 'hidden',
        padding: '7px 8px',
        rowGap: 5,
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
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 12,
        fontWeight: 700,
        letterSpacing: '0.01em',
        padding: '4px 11px',
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
    {/* Header re-balanced to mirror the firing card's height so nothing jumps
        between tabs: identity on the left, the state chip in the verdict slot. */}
    <div
      style={{
        alignItems: 'center',
        background: 'rgba(20, 23, 33, 0.98)',
        borderBottom: '1px solid rgba(255,255,255,0.055)',
        display: 'flex',
        gap: 8,
        justifyContent: 'space-between',
        minHeight: 34,
        overflow: 'hidden',
        padding: '6px 10px',
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
        <span style={{ color: 'var(--text-main)', fontSize: 18, fontWeight: 850, letterSpacing: '-0.01em', lineHeight: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {ticker}
        </span>
        {data.name ? (
          <span style={{ color: 'var(--text-faint)', fontSize: 10, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {data.name}
          </span>
        ) : null}
      </div>
      <StateChip state={data.state} />
    </div>

    <div style={{ display: 'flex', height: 'clamp(180px, 11vw, 240px)', minHeight: 180, position: 'relative' }}>
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
