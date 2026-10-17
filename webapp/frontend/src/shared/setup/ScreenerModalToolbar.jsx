import { useEffect } from 'react';
import { tierColor, signColor } from '../presentation/theme';
import { fx, fmtSignedPctFrac } from '../formatting/format';
import { dailyChangeFrac } from './screenerCardData';
import { lensKeyAction, tradingViewUrl } from './lensActions';

const INTERVAL_TABS = [
  { key: 'D', label: 'D', name: 'Daily' },
  { key: 'W', label: 'W', name: 'Weekly' },
  { key: 'M', label: 'M', name: 'Monthly' },
];

// TradingView-style D/W/M switcher: which of the three panes is the BIG one (Fri 17/10/2026; the
// other two take the side column). Weekly/Monthly are disabled when the row predates the
// higher-timeframe read (no resampled candles in payload).
function IntervalTabs({ interval, onIntervalChange, hasWeekly, hasMonthly }) {
  const enabled = { D: true, W: hasWeekly, M: hasMonthly };
  return (
    <div
      role="tablist"
      aria-label="Chart timeframe"
      style={{
        alignItems: 'stretch',
        border: '1px solid var(--border-color)',
        borderRadius: 6,
        display: 'flex',
        height: 28,
        overflow: 'hidden',
      }}
    >
      {INTERVAL_TABS.map((tab, index) => {
        const active = interval === tab.key;
        const ok = enabled[tab.key];
        return (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={active}
            disabled={!ok}
            onClick={() => ok && onIntervalChange(tab.key)}
            title={ok ? `${tab.name} in the big pane` : `${tab.name} — needs more history`}
            style={{
              background: active ? 'var(--myth-soft)' : 'transparent',
              border: 'none',
              borderLeft: index === 0 ? 'none' : '1px solid var(--border-color)',
              color: !ok ? 'var(--text-faint)' : active ? 'var(--myth)' : 'var(--text-muted)',
              cursor: ok ? 'pointer' : 'default',
              fontFamily: 'inherit',
              fontSize: 12,
              fontWeight: 700,
              minWidth: 30,
              padding: '0 10px',
            }}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

// W / L / T while the lens is open (operator 2026-10-03, suggestion #1): the
// same acts as the top bar's buttons, and only where that button is drawn, so W
// in a lens with no star does nothing.
function useLensActionKeys(ticker, onToggleWatchlist, onToggleLike, onToggleFix) {
  useEffect(() => {
    const onKey = (event) => {
      const action = lensKeyAction(event);
      if (action === 'watch' && onToggleWatchlist) onToggleWatchlist(ticker);
      else if (action === 'like' && onToggleLike) onToggleLike(ticker);
      else if (action === 'tradingview') window.open(tradingViewUrl(ticker), '_blank', 'noopener,noreferrer');
      else if (action === 'fixbox' && onToggleFix) onToggleFix();
      else return;
      event.preventDefault();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [ticker, onToggleWatchlist, onToggleLike, onToggleFix]);
}

export default function ScreenerModalToolbar({
  data, onClose, onNext, onPrev, ticker, interval, onIntervalChange, hasWeekly, hasMonthly,
  watchlisted, onToggleWatchlist, liked, onToggleLike, position, skin = 'dark', onToggleSkin,
  fixing = false, onToggleFix,
}) {
  const changePct = dailyChangeFrac(data?.candles);
  useLensActionKeys(ticker, onToggleWatchlist, onToggleLike, onToggleFix);
  return (
    <header style={{
      alignItems: 'center',
      background: 'var(--lens-toolbar-bg)',
      borderBottom: '1px solid var(--border-color)',
      display: 'flex',
      gap: 16,
      justifyContent: 'space-between',
      minHeight: 52,
      padding: '8px 14px',
    }} className="screener-modal-toolbar">
      <div style={{ alignItems: 'center', display: 'flex', gap: 12, minWidth: 0 }}>
        <strong style={{ color: tierColor(data.tier), fontFamily: "'JetBrains Mono', monospace", fontSize: 22 }}>
          {ticker}
        </strong>
        <span style={{
          border: `1px solid ${tierColor(data.tier)}55`,
          borderRadius: 6,
          color: tierColor(data.tier),
          fontSize: 11,
          fontWeight: 800,
          padding: '2px 7px',
        }}>
          {data.tier} TIER
        </span>
        <IntervalTabs
          hasMonthly={hasMonthly}
          hasWeekly={hasWeekly}
          interval={interval}
          onIntervalChange={onIntervalChange}
        />
        <span style={{ color: 'var(--text-main)', fontFamily: "'JetBrains Mono', monospace", fontSize: 16, fontWeight: 700 }}>
          ${fx(data.price, 2)}
        </span>
        {changePct != null && (
          <span style={{ color: signColor(changePct) || 'var(--text-muted)', fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700 }}>
            {fmtSignedPctFrac(changePct, 1)}
          </span>
        )}
        <span style={{ color: 'var(--text-muted)', fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {data.setup}
        </span>
      </div>
      <div style={{ alignItems: 'center', display: 'flex', gap: 8 }}>
        {/* The card's own acts, so he can walk the list with Next and act on each
            chart without closing it. Star and heart only where the host can save
            them (the screener grid); TradingView needs only the ticker. */}
        {onToggleWatchlist && (
          <button
            type="button"
            className="btn btn-icon lens-toggle"
            aria-pressed={Boolean(watchlisted)}
            aria-label="Watchlist"
            aria-keyshortcuts="W"
            title={watchlisted ? 'Remove from watchlist (W)' : 'Save to watchlist (W)'}
            onClick={() => onToggleWatchlist(ticker)}
          >
            {watchlisted ? '★' : '☆'}
          </button>
        )}
        {onToggleLike && (
          <button
            type="button"
            className="btn btn-icon lens-toggle"
            aria-pressed={Boolean(liked)}
            aria-label="Like"
            aria-keyshortcuts="L"
            title={liked ? 'Liked, press L to unlike' : 'Like this setup, the kind you want more of (L)'}
            onClick={() => onToggleLike(ticker)}
          >
            {liked ? '♥' : '♡'}
          </button>
        )}
        <a
          className="btn"
          href={tradingViewUrl(ticker)}
          target="_blank"
          rel="noopener noreferrer"
          aria-keyshortcuts="T"
          title={`Open ${ticker} on TradingView (T)`}
        >
          ↗ TV
        </a>
        {/* "Fix the box" (Fri 17/10/2026): he corrects the reader's two lines on the daily chart; the fix is
            saved beside the reader's pair, the material the chooser is learned from later. Drawn only where
            the daily is a two-eyes read (the host hands in the toggle). */}
        {onToggleFix && (
          <button
            type="button"
            className="btn lens-toggle"
            aria-pressed={Boolean(fixing)}
            aria-label="Fix the box"
            aria-keyshortcuts="B"
            title={fixing ? 'Fixing the box: click the resistance bar, then the support bar (B to stop)' : 'Fix the box: draw your two lines on the daily chart (B)'}
            onClick={onToggleFix}
          >
            {fixing ? 'fixing the box' : 'fix the box'}
          </button>
        )}
        {/* The lens's skin, paper or dark (Thu 16/10/2026); the choice is kept per browser. */}
        {onToggleSkin && (
          <button
            type="button"
            className="btn btn-icon"
            aria-pressed={skin === 'paper'}
            aria-label="Paper skin"
            title={skin === 'paper' ? 'Paper skin on: switch the lens to dark' : 'Switch the lens to paper (white blocks)'}
            onClick={onToggleSkin}
          >
            {skin === 'paper' ? '☾' : '☼'}
          </button>
        )}
        {/* "– / 36" once the chart drops out of the list (un-starred on the Watchlist
            tier): the slot stays, so the star beside it never slides from under the pointer. */}
        {position && (
          <span
            className="lens-position"
            aria-label={position.n ? `Setup ${position.n} of ${position.total}` : `Not in this list of ${position.total}`}
          >
            {position.n ?? '–'} / {position.total}
          </span>
        )}
        {/* Prev/Next only where the host can step (screener grid, weekly review); a button that does nothing is not drawn. */}
        {onPrev && <button type="button" className="btn" onClick={onPrev}>Prev</button>}
        {onNext && <button type="button" className="btn" onClick={onNext}>Next</button>}
        <button type="button" className="btn btn-icon" onClick={onClose} title="Close" aria-label="Close">✕</button>
      </div>
    </header>
  );
}
