import React from 'react';
import ScreenerCard, { WatchlistButton } from '../../../shared/setup/ScreenerCard';
import ScreenerMiniChart from '../../../shared/charts/ScreenerMiniChart';
import { CANDLE_REASON_COPY } from '../presentation/watchlistChartData';
import { dailyChangeFrac, asOfDate } from '../../../shared/setup/screenerCardData';
import { fx, fmtDay, fmtSignedPctFrac } from '../../../shared/formatting/format';
import { signColor } from '../../../shared/presentation/theme';
import useChartState from '../hooks/useChartState';

// The state word for a name the scan did not list (points 22 and 24), read
// off the wire already resolved: "not scanned: under the 50-day average
// (1.3 ranges)", or the lines the walk found with their facts.
const stateCopy = (state) => {
  if (!state?.state) return null;
  let line = state.why ? `${state.state}: ${state.why}` : state.state;
  if (state.distance_ranges != null) line += ` (${fx(state.distance_ranges, 1)} ranges)`;
  if (state.R != null && state.S != null) {
    line += ` · R ${fx(state.R, 2)} / S ${fx(state.S, 2)} · open ${fmtDay(state.open)}`;
    if (state.age != null) line += ` · ${fx(state.age, 0)} days`;
    if (state.turns_at_r != null) line += ` · turns ${fx(state.turns_at_r, 0)} / ${fx(state.turns_at_s, 0)}`;
  }
  return line;
};

// The Watchlist page's bottom section: one full screener-grid card per starred
// name. A scan-backed name renders the REAL ScreenerCard — same header, chart
// well, and tag row as the screener grid, fed the scan row wholesale. An
// off-scan name renders the clean-card branch on the HealthCard precedent: the
// same shell and mini chart fed the endpoint's bare daily candles, with a
// NEUTRAL (untiered) ticker — the absence of a ranked color is itself the "no
// engine read" tell. One source per card, never mixed. Clicking any card puts
// its ticker on the big chart above.

const cardShellStyle = {
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-sm)',
  cursor: 'pointer',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
  // The FULL transition list the firing card declares: an inline `transition`
  // overrides the screener-card class's list entirely, so omitting transform/
  // box-shadow here would make this card SNAP on hover beside a scan card
  // that glides — mixed rows must answer hover with the same physics.
  transition: 'border-color 0.16s ease, background 0.16s ease, box-shadow 0.18s ease, transform 0.18s cubic-bezier(0.22, 1, 0.36, 1)',
};

const hoverOn = (event) => {
  event.currentTarget.style.borderColor = 'rgba(79,207,196,0.65)';
  event.currentTarget.style.background = '#242837';
};

const hoverOff = (event) => {
  event.currentTarget.style.borderColor = 'var(--border-color)';
  event.currentTarget.style.background = 'var(--bg-panel)';
};

// Covers both the 'clean' kind (bare candles, no engine read) and the 'void'
// kind (no candles at all — the well carries the named reason instead). The
// well grows (flex 1 0 auto) so a clean card beside a taller scan card grows its
// CHART to match, never a blank bottom band.
function CleanCard({ ticker, card, onSelect, onRemove }) {
  const candles = card.data?.candles || [];
  const changePct = dailyChangeFrac(candles);
  const lastClose = candles.length ? candles[candles.length - 1]?.close : null;
  const stateLine = stateCopy(useChartState(ticker, candles.length > 0));
  return (
    <div
      className="screener-card"
      role="button"
      tabIndex={0}
      aria-label={`Show ${ticker} on the big chart — price and volume only`}
      onClick={() => onSelect(ticker)}
      onKeyDown={(event) => {
        if (event.target !== event.currentTarget) return;
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onSelect(ticker);
        }
      }}
      style={cardShellStyle}
      onMouseEnter={hoverOn}
      onMouseLeave={hoverOff}
    >
      {/* The scan card's two-row shell (2026-10-04): the stock and its price on
          top, the state line under them (the part that gives way). An empty
          slot stands where the scan card's ♡ sits, so the star column lines up
          across both card kinds in a mixed row. */}
      <div className="screener-card-head">
        <div className="screener-card-head-row">
          <span style={{ color: 'var(--text-main)', flexShrink: 0, fontSize: 17, fontWeight: 850, letterSpacing: '-0.01em', lineHeight: 1, whiteSpace: 'nowrap' }}>
            {ticker}
          </span>
          <span style={{ color: 'var(--text-faint)', flexShrink: 0, fontFamily: "'JetBrains Mono', monospace", fontSize: 11, marginLeft: 'auto', whiteSpace: 'nowrap' }}>
            {asOfDate(candles)}
          </span>
          <span style={{ alignItems: 'baseline', display: 'flex', flexShrink: 0, gap: 6 }}>
            <span style={{ color: 'var(--text-main)', fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700, whiteSpace: 'nowrap' }}>
              ${fx(lastClose, 2)}
            </span>
            {changePct != null && (
              <span style={{ color: signColor(changePct) || 'var(--text-muted)', fontFamily: "'JetBrains Mono', monospace", fontSize: 12, fontWeight: 700, whiteSpace: 'nowrap' }}>
                {fmtSignedPctFrac(changePct, 1)}
              </span>
            )}
          </span>
          <span style={{ display: 'flex', flexShrink: 0, gap: 4, marginLeft: 2 }}>
            <WatchlistButton active onToggle={() => onRemove(ticker)} />
            <span aria-hidden="true" style={{ width: 20 }} />
          </span>
        </div>
        <div className="screener-card-head-row is-sub">
          <span style={{ color: 'var(--text-faint)', fontSize: 11, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={stateLine || undefined}>
            {stateLine || 'price & volume only — no engine read'}
          </span>
        </div>
      </div>
      {/* Width-locked like the scan card's well (1.9:1, 2026-10-02), and free
          to GROW (flex 1 0 auto) when a taller scan card shares the row. */}
      <div className="screener-card-well" style={{ aspectRatio: 'var(--card-chart-aspect)', display: 'flex', flex: '1 0 auto', minHeight: 'var(--card-chart-min-h)', position: 'relative' }}>
        {candles.length ? (
          <ScreenerMiniChart ticker={ticker} data={card.data} />
        ) : (
          <span className="wl-card-void">
            {CANDLE_REASON_COPY[card.reason] || CANDLE_REASON_COPY.error}
          </span>
        )}
      </div>
    </div>
  );
}

// Memoized so the page's 60s price poll (which changes no grid prop) never
// re-renders N cards and their per-card candle clones; the select handlers
// are useCallback'd by the page for the same reason.
const WatchlistCardGrid = React.memo(function WatchlistCardGrid({
  tickers, cards, selected, watchlist,
  onSelect, onToggleWatchlist, passed, onTogglePassed,
}) {
  return (
    <div className="wl-card-grid">
      {tickers.map((ticker) => {
        const card = cards[ticker] || { kind: 'void', reason: 'loading' };
        return (
          <div
            aria-current={ticker === selected || undefined}
            className={`wl-card${ticker === selected ? ' selected' : ''}`}
            key={ticker}
          >
            {card.kind === 'scan' ? (
              <ScreenerCard
                data={card.data}
                onClick={onSelect}
                onTogglePassed={onTogglePassed}
                onToggleWatchlist={onToggleWatchlist}
                passed={passed.has(ticker)}
                ticker={ticker}
                watchlisted={watchlist.has(ticker)}
              />
            ) : (
              <CleanCard
                card={card}
                onRemove={onToggleWatchlist}
                onSelect={onSelect}
                ticker={ticker}
              />
            )}
          </div>
        );
      })}
    </div>
  );
});

export default WatchlistCardGrid;
