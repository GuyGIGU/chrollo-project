import React from 'react';
import { TagRow } from './SetupTags';
import { ScoreBreakdownPills } from './ScoreBreakdown';
import ScreenerMiniChart from './ScreenerMiniChart';
import { explainTip } from './tooltipText';
import { tierColor } from '../theme';

const scoreLabel = (value) => (
  value == null || !Number.isFinite(Number(value)) ? '-' : `${Math.round(Number(value))}`
);

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
      title={explainTip({
        what: `Earnings are scheduled in ${days} day${days === 1 ? '' : 's'} (${info.date}).`,
        why: 'Near-term earnings can override a clean technical setup with gap risk and volatility.',
        use: 'Treat it as a timing warning and decide manually whether the setup is still worth tracking before the report.',
      })}
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
        background: active ? 'var(--success-bg)' : 'transparent',
        border: '1px solid var(--border-color)',
        borderRadius: 6,
        color: active ? 'var(--success)' : '#6b6b7a',
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

// Three-zone header: a quiet utility rail (saved/considered), an identity block
// led by the ticker, and a verdict block where the SCORE is the hero figure the
// eye lands on first. Setup label, earnings, and sub-scores recede beneath their
// leaders so the card reads as "rank + score" at a glance during triage.
function CardHeader({ data, earnings, onTogglePassed, onToggleWatchlist, passed, ticker, watchlisted }) {
  const score = scoreLabel(data.score);

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
            {score}
          </span>
        </div>
        <ScoreBreakdownPills subScores={data.sub_scores} className="score-breakdown-compact" />
      </div>
    </div>
  );
}

// One timeframe's read: trend arrow (color = up/down/neutral), the structural
// state (re-accum / consol+phase / stage-2 / —), and a nesting mark when the
// daily base sits inside this timeframe's box. Re-accumulation is the premium
// case, so it takes the S-tier amber.
function TimeframeCell({ tf, stage2, trendState, inConsol, phase, reaccum, nested }) {
  const trend = trendState === 'up' ? { sym: '▲', col: 'var(--success)' }
    : trendState === 'down' ? { sym: '▼', col: 'var(--danger)' }
      : trendState === 'neutral' ? { sym: '▬', col: '#8b949e' }
        : { sym: '·', col: 'var(--text-faint)' };
  let state = '—';
  let stateCol = 'var(--text-faint)';
  if (reaccum) { state = `Re-accum${phase ? ` ${phase}` : ''}`; stateCol = '#ff9f43'; }
  else if (inConsol) { state = `Consol${phase ? ` ${phase}` : ''}`; stateCol = '#58a6ff'; }
  else if (stage2) { state = 'Uptrend'; stateCol = 'var(--success)'; }
  else if (trendState == null || trendState === 'unknown') { state = 'no data'; }
  else if (trendState === 'down') { state = 'downtrend'; stateCol = 'var(--danger)'; }
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
    <div title={title} style={{ alignItems: 'center', display: 'flex', flex: 1, gap: 5, minWidth: 0 }}>
      <span style={{ color: 'var(--text-faint)', fontSize: 10, fontWeight: 700, letterSpacing: '0.08em' }}>{tf}</span>
      <span style={{ color: trend.col, fontSize: 13, lineHeight: 1 }}>{trend.sym}</span>
      <span style={{ color: stateCol, fontSize: 11, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{state}</span>
      {nested ? <span style={{ color: '#ff9f43', fontSize: 13, lineHeight: 1 }}>⊂</span> : null}
    </div>
  );
}

// The always-visible weekly + monthly context band: the SAME Trend+Box engine
// read one and two timeframes up. Hidden only on rows that predate the read.
function TimeframeBand({ data }) {
  if (data.htf_w_trend_state == null && data.htf_m_trend_state == null) return null;
  return (
    <div style={{ alignItems: 'center', background: 'var(--bg-main)', borderTop: '1px solid var(--border-color)', display: 'flex', gap: 8, padding: '8px' }}>
      <span style={{ color: 'var(--text-faint)', fontSize: 8, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', flexShrink: 0 }}>HTF</span>
      <TimeframeCell tf="W" stage2={data.htf_w_stage2} trendState={data.htf_w_trend_state} inConsol={data.htf_w_in_consol} phase={data.htf_w_phase} reaccum={data.htf_w_reaccum} nested={data.htf_w_daily_nested} />
      <span style={{ alignSelf: 'stretch', background: 'var(--border-color)', width: 1 }} />
      <TimeframeCell tf="M" stage2={data.htf_m_stage2} trendState={data.htf_m_trend_state} inConsol={data.htf_m_in_consol} phase={data.htf_m_phase} reaccum={data.htf_m_reaccum} nested={data.htf_m_daily_nested} />
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

const ScreenerCard = React.memo(({ ticker, data, earnings, watchlisted, onToggleWatchlist, passed, onTogglePassed, onClick, onDrilldown }) => (
  <div
    className="screener-card"
    role="button"
    tabIndex={0}
    aria-label={`Open ${ticker} chart — ${data.setup}, tier ${data.tier}, score ${scoreLabel(data.score)}. Press W to save to watchlist, C to mark considered.`}
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
      onTogglePassed={onTogglePassed}
      onToggleWatchlist={onToggleWatchlist}
      passed={passed}
      ticker={ticker}
      watchlisted={watchlisted}
    />
    <div style={{ display: 'flex', height: 'clamp(180px, 11vw, 240px)', minHeight: 180, position: 'relative' }}>
      <ScreenerMiniChart ticker={ticker} data={data} />
    </div>
    <TimeframeBand data={data} />
    <TagRow
      subScores={data.sub_scores}
      flags={{
        phaseDInner: data.phase_d_inner,
        rTouchVolZ: data.r_touch_vol_z,
        sTouchVolZ: data.s_touch_vol_z,
        contractionVolTrend: data.contraction_vol_trend,
        cogEnd: data.bin_b_cog_end,
        cogCrossings: data.bin_b_cog_crossings,
        traversalDensity: data.traversal_density,
        cogRng: data.bin_b_cog_rng,
        cogCorr: data.bin_b_cog_corr,
        binCPresent: data.bin_c_present,
        binCType: data.bin_c_type,
        binCUndercutAtr: data.bin_c_undercut_atr,
        binCRecoveryBars: data.bin_c_recovery_bars,
        binCSpringVolZ: data.bin_c_spring_vol_z,
        htfWeeklyReaccum: data.htf_w_reaccum,
        htfWeeklyPhase: data.htf_w_phase,
        htfDailyNested: data.htf_w_daily_nested,
        htfMonthlyReaccum: data.htf_m_reaccum,
        htfMonthlyTrendState: data.htf_m_trend_state,
        lpsStretchAtr: data.lps_stretch_atr,
        lpsStretchBox: data.lps_stretch_box,
        lastSupperPullbackPct: data.last_supper_pullback_from_extension_pct,
        lastSupperSourceBoxAge: data.last_supper_source_box_age,
        lastSupperReclaimQuality: data.last_supper_reclaim_quality,
      }}
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
        onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--accent-blue)'; }}
        onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)'; }}
      >
        Members →
      </button>
    )}
  </div>
));

export default ScreenerCard;
