import React from 'react';
import ScreenerCard, { WatchlistButton } from '../ScreenerCard';
import ScreenerMiniChart from '../ScreenerMiniChart';
import { CANDLE_REASON_COPY } from '../../utils/watchlistChartData';
import { dailyChangeFrac, asOfDate } from '../../utils/screenerCardData';
import { fx, fmtDay, fmtSignedPctFrac } from '../../utils/format';
import { signColor } from '../../theme';
import useChartState from '../../hooks/useChartState';

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
// well takes flex:1 so a clean card beside a taller scan card grows its CHART
// to match, never a blank bottom band.
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
      <div
        style={{
          background: 'rgba(20, 23, 33, 0.5)',
          borderBottom: '1px solid rgba(255,255,255,0.055)',
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
          padding: '9px 10px',
          position: 'relative',
        }}
      >
        {/* right:33 reserves the scan card's second toggle slot, so the star
            column lines up across both card kinds in a mixed row. */}
        <div style={{ position: 'absolute', right: 33, top: 8 }}>
          <WatchlistButton active onToggle={() => onRemove(ticker)} />
        </div>
        <div style={{ alignItems: 'center', display: 'flex', gap: 7, minWidth: 0, paddingRight: 52 }}>
          <span style={{ color: 'var(--text-main)', fontSize: 19, fontWeight: 850, letterSpacing: '-0.01em', lineHeight: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {ticker}
          </span>
          <span style={{ color: 'var(--text-faint)', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, marginLeft: 'auto', whiteSpace: 'nowrap' }}>
            {asOfDate(candles)}
          </span>
        </div>
        <div style={{ alignItems: 'center', display: 'flex', gap: 10, minWidth: 0 }}>
          <span style={{ color: 'var(--text-faint)', fontSize: 11, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={stateLine || undefined}>
            {stateLine || 'price & volume only — no engine read'}
          </span>
          <span style={{ alignItems: 'baseline', display: 'flex', gap: 6, marginLeft: 'auto' }}>
            <span style={{ color: 'var(--text-main)', fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700 }}>
              ${fx(lastClose, 2)}
            </span>
            {changePct != null && (
              <span style={{ color: signColor(changePct) || 'var(--text-muted)', fontFamily: "'JetBrains Mono', monospace", fontSize: 12, fontWeight: 700 }}>
                {fmtSignedPctFrac(changePct, 1)}
              </span>
            )}
          </span>
        </div>
      </div>
      <div className="screener-card-well" style={{ display: 'flex', flex: 1, minHeight: 'var(--card-chart-h)', position: 'relative' }}>
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
