import React, { useState } from 'react';
import { TagRow } from './SetupTags';
import ScreenerMiniChart from '../charts/ScreenerMiniChart';
import { explainTip } from '../formatting/tooltipText';
import { healthStateMeta } from './healthStateData';
import { tierColor, signColor } from '../presentation/theme';
import { fx, fmtSignedPctFrac } from '../formatting/format';
import { dailyChangeFrac, asOfDate, htfStateLabel } from './screenerCardData';
import { groupTitle, hasGroupRead } from './groupRead';
import { dialogOpenOutside, hasCommandModifier } from '../navigation/keyboardGuard';
import FundamentalsCardPage from './FundamentalsCardPage';
import { hasFundamentalsSheet } from './fundamentalsSheetRead';

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

// The card's second page (2026-10-12, his "a second page in the Mini Chart"): F flips
// the chart well to the business and back. Shown only when the scan carried a sheet.
function PageButton({ active, onToggle }) {
  return (
    <button
      onClick={(event) => {
        event.stopPropagation();
        onToggle();
      }}
      aria-pressed={active}
      title={active ? 'Back to the chart (F)' : 'Show the fundamentals (F)'}
      style={{
        background: active ? 'rgba(79,207,196,0.14)' : 'rgba(20,23,33,0.7)',
        border: `1px solid ${active ? 'var(--myth)' : 'var(--border-color)'}`,
        borderRadius: 5,
        color: active ? 'var(--myth)' : 'var(--text-faint)',
        cursor: 'pointer',
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10,
        fontWeight: 800,
        height: 20,
        lineHeight: 1,
        pointerEvents: 'auto',
        width: 20,
      }}
    >
      F
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

// The weekly / monthly read, one line each, for the ticker's tooltip: it had its own row under the ticker line
// until the card became Finviz's chart (Thu 29/10/2026), where there is room for one line only.
function htfTitle(data) {
  if (data.htf_w_trend_state == null && data.htf_m_trend_state == null) return undefined;
  const line = (name, stage2, trendState, inConsol, phase, reaccum, nested) => {
    const { label } = htfStateLabel({ stage2, trendState, inConsol, phase, reaccum });
    return `${name}: ${label}, trend ${trendState || 'unknown'}${nested ? ', the daily base nests inside its box' : ''}`;
  };
  return [
    line('Weekly', data.htf_w_stage2, data.htf_w_trend_state, data.htf_w_in_consol, data.htf_w_phase, data.htf_w_reaccum, data.htf_w_daily_nested),
    line('Monthly', data.htf_m_stage2, data.htf_m_trend_state, data.htf_m_in_consol, data.htf_m_phase, data.htf_m_reaccum, data.htf_m_daily_nested),
  ].join('\n');
}

const monoFaint = { color: 'var(--text-faint)', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, whiteSpace: 'nowrap' };

// Finviz's ticker line, INSIDE the chart (Thu 29/10/2026, his "Finviz Daily, exactly"): the ticker, tier and
// sector ETF, then, pushed right, the as-of date, the price and its daily % change, and the toggles. It was a
// two-row lip over the chart from 2026-10-04; the weekly / monthly read it carried is the ticker's tooltip now.
// The shell (.screener-card-head) is shared with the health card, so every card kind's line sits the same.
// Score, setup name, and the next-earnings date live in the click-through detail lens, keeping the card face
// to the chart itself.
function CardHeader({ data, ticker, watchlisted, onToggleWatchlist, liked, onToggleLike, page, onTogglePage, fixed = null }) {
  const changePct = dailyChangeFrac(data.candles);

  return (
    <div className="screener-card-head">
      <div className="screener-card-head-row">
        <span title={htfTitle(data)} style={{ color: tierColor(data.tier), flexShrink: 0, fontSize: 15, fontWeight: 850, letterSpacing: '-0.01em', lineHeight: 1, pointerEvents: 'auto', whiteSpace: 'nowrap' }}>
          {ticker}
        </span>
        <span style={tierBadgeStyle(data.tier)}>{data.tier}</span>
        {/* He fixed this box on the lens (Sat 18/10/2026): one glyph in the operator hue, the backend's sentence as its title. */}
        {fixed ? <span className="card-fixed-mark" title={fixed} aria-label={fixed}>✎</span> : null}
        {/* The sector ETF alone: the industry's full name came off the card (Thu 29/10/2026, his "remove the full
            sector name from the mini chart"; shown from 2026-10-23); it stays in this tag's tooltip and on the lens. */}
        {data.sector_etf ? (
          <span style={{ alignItems: 'center', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-xs)', color: 'var(--text-muted)', display: 'inline-flex', flexShrink: 0, fontFamily: "'JetBrains Mono', monospace", fontSize: 11, height: 15, lineHeight: 1, padding: '0 4px', pointerEvents: 'auto' }}
            title={hasGroupRead(data) ? groupTitle(data.group) : undefined}>
            {data.sector_etf}
          </span>
        ) : null}

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
          {onTogglePage ? <PageButton active={page === 'fundamentals'} onToggle={onTogglePage} /> : null}
        </span>
      </div>
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

const FiringCard = React.memo(({ ticker, data, watchlisted, onToggleWatchlist, liked, onToggleLike, onClick, onDrilldown, fixed = null }) => {
  const [page, setPage] = useState('chart');
  const hasSheet = hasFundamentalsSheet(data);
  const togglePage = hasSheet ? () => setPage((now) => (now === 'chart' ? 'fundamentals' : 'chart')) : null;
  return (
  <div
    className="screener-card"
    data-ticker={ticker}
    role="button"
    tabIndex={0}
    aria-label={`Open ${ticker} chart, tier ${data.tier}. Press W to ${watchlisted ? 'remove from' : 'save to'} watchlist, L to ${liked ? 'unlike' : 'like'}${hasSheet ? ', F for the fundamentals' : ''}.`}
    onClick={() => onClick(ticker)}
    onKeyDown={(event) => {
      // Only act on keys aimed at the card itself, not ones bubbling up from the
      // inner toggle buttons (otherwise Enter/Space on a focused toggle would
      // also open the card). Enter/Space open it; W/L are power-user toggles that
      // keep the per-card engagement a like depends on — a deliberate
      // alternative to mass-marking a whole page at once.
      if (event.target !== event.currentTarget) return;
      // Stand down under the big chart (it keeps its own W/L for the chart on
      // screen; this card stays focused behind it) and for Ctrl+L and the like.
      if (hasCommandModifier(event) || dialogOpenOutside(event.currentTarget)) return;
      // A held key does not repeat, as in the lens: holding W must not flicker the
      // star and send one watchlist write per auto-repeat.
      if (event.repeat) return;
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        onClick(ticker);
      } else if (event.key === 'w' || event.key === 'W') {
        event.preventDefault();
        onToggleWatchlist(ticker);
      } else if (event.key === 'l' || event.key === 'L') {
        event.preventDefault();
        onToggleLike(ticker);
      } else if ((event.key === 'f' || event.key === 'F') && togglePage) {
        event.preventDefault();
        togglePage();
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
    <div className="screener-card-well" style={chartWellStyle}>
      <CardHeader
        data={data}
        fixed={fixed}
        liked={liked}
        onToggleLike={onToggleLike}
        onToggleWatchlist={onToggleWatchlist}
        onTogglePage={togglePage}
        page={page}
        ticker={ticker}
        watchlisted={watchlisted}
      />
      {/* The chart stays mounted under the page, so flipping back costs no redraw. */}
      <ScreenerMiniChart ticker={ticker} data={data} />
      {page === 'fundamentals' && hasSheet ? <FundamentalsCardPage data={data} /> : null}
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
  );
});

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
        padding: '2px 10px', // fits the header's 20px top row (was 4px 11px)
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
    {/* The firing card's ticker line, inside the chart (Thu 29/10/2026), so nothing jumps between tabs: the
        ticker, the name (it gives way), the state chip pushed right. */}
    <div style={chartWellStyle}>
      <div className="screener-card-head">
        <div className="screener-card-head-row">
          <span style={{ color: 'var(--text-main)', flexShrink: 0, fontSize: 15, fontWeight: 850, letterSpacing: '-0.01em', lineHeight: 1, whiteSpace: 'nowrap' }}>
            {ticker}
          </span>
          {data.name ? (
            <span title={data.name} style={{ color: 'var(--text-faint)', fontSize: 11, minWidth: 0, overflow: 'hidden', pointerEvents: 'auto', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {data.name}
            </span>
          ) : null}
          <span style={{ flexShrink: 0, marginLeft: 'auto' }}><StateChip state={data.state} /></span>
        </div>
      </div>
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
