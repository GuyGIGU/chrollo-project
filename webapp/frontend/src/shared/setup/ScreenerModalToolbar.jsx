import { useEffect } from 'react';
import { tierColor, signColor } from '../presentation/theme';
import { fx, fmtMoneyCompact, fmtSignedPctFrac, EMPTY } from '../formatting/format';
import { asOfDate, dailyChangeFrac } from './screenerCardData';
import { lensKeyAction, tradingViewUrl } from './lensActions';

// THE LENS IS FINVIZ'S QUOTE PAGE (operator Thu 29/10/2026, "base our advanced chart page on their page
// ... notice how everything is sitting compact and easy to read"): a slim bar with the way back and the
// pager, then the quote (ticker, company, price), a row of tabs with the stock's chips and its acts on the
// right, then the chart box with its own toolbar. This file draws the bar, the quote and the chart toolbar;
// ScreenerModal lays them out.

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

// The stock's chips, Finviz's row of sector · industry · country · cap: what the payload carries.
// Each chip says what it is (Thu 29/10/2026, his "say the sector in the advanced chart"): Sector, Industry, Cap, Setup.
function quoteChips(data) {
  const snap = data?.fund_sheet?.snapshot ?? {};
  const sector = snap.sector || data?.sector_name;
  return [
    { k: 'Sector', v: sector ? `${sector}${data?.sector_etf ? ` (${data.sector_etf})` : ''}` : data?.sector_etf },
    { k: 'Industry', v: snap.industry || data?.group?.industry },
    { k: 'Cap', v: data?.market_cap > 0 ? fmtMoneyCompact(data.market_cap) : null },
    { k: 'Setup', v: data?.setup },
  ].filter((chip) => chip.v);
}

// The slim bar over the page: the way back (Finviz's "‹ Screener") and, on the right, the pager, the skin
// and the close. The lens's keys live here, because this bar is drawn by every host.
export function LensNavBar({
  ticker, onClose, onNext, onPrev, position, skin = 'dark', onToggleSkin,
  onToggleWatchlist, onToggleLike, onToggleFix, backLabel = 'Back',
}) {
  useLensActionKeys(ticker, onToggleWatchlist, onToggleLike, onToggleFix);
  return (
    <div className="screener-modal-toolbar lens-nav-bar">
      <button type="button" className="lens-back" onClick={onClose} title="Close (Esc)">‹ {backLabel}</button>
      <div className="lens-nav-acts">
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
        {onPrev && <button type="button" className="btn btn-sm" onClick={onPrev}>Prev</button>}
        {onNext && <button type="button" className="btn btn-sm" onClick={onNext}>Next</button>}
        {/* The lens's skin, paper or dark (Thu 16/10/2026); the choice is kept per browser. */}
        {onToggleSkin && (
          <button
            type="button"
            className="btn btn-icon btn-sm"
            aria-pressed={skin === 'paper'}
            aria-label="Paper skin"
            title={skin === 'paper' ? 'Paper skin on: switch the lens to dark' : 'Switch the lens to paper (white blocks)'}
            onClick={onToggleSkin}
          >
            {skin === 'paper' ? '☾' : '☼'}
          </button>
        )}
        <button type="button" className="btn btn-icon btn-sm" onClick={onClose} title="Close" aria-label="Close">✕</button>
      </div>
    </div>
  );
}

// The quote, Finviz's header: the ticker big, the company in blue, the tier; the price big on the right
// with the day's change under its date. Then the tabs row: the panel's pages on the left (the host hands
// them in), the chips and the card's own acts on the right.
export function LensQuote({
  data, ticker, tabs = null, watchlisted, onToggleWatchlist, liked, onToggleLike, fixedSummary = null,
}) {
  const changePct = dailyChangeFrac(data?.candles);
  const name = data?.fund_sheet?.snapshot?.name;
  const asOf = asOfDate(data?.candles);
  return (
    <header className="lens-quote">
      <div className="lens-quote-row">
        <div className="lens-quote-id">
          <span className="lens-quote-ticker" style={{ color: tierColor(data.tier) }}>{ticker}</span>
          {name ? <span className="lens-quote-name">{name}</span> : null}
          <span className="lens-quote-tier" style={{ borderColor: `${tierColor(data.tier)}55`, color: tierColor(data.tier) }}>
            {data.tier} TIER
          </span>
          {/* A fixed box is visibly a fixed box (Sat 18/10/2026): one glyph, one word, the operator hue; the
              sentence is the backend's (what was fixed, and when). */}
          {fixedSummary && (
            <span className="lens-fixed-mark" title={fixedSummary} aria-label={fixedSummary}>✎ fixed</span>
          )}
        </div>
        <div className="lens-quote-price">
          <span className="lens-quote-last">${fx(data.price, 2)}</span>
          <span className="lens-quote-change">
            {asOf !== EMPTY ? <small>{asOf}</small> : null}
            {changePct != null && (
              <b style={{ color: signColor(changePct) || 'var(--text-muted)' }}>{fmtSignedPctFrac(changePct, 2)}</b>
            )}
          </span>
        </div>
      </div>
      <div className="lens-quote-tabs">
        <div className="lens-quote-pages">{tabs}</div>
        <div className="lens-quote-acts">
          {quoteChips(data).map((chip) => (
            <span className="lens-chip" key={chip.k}><span className="lens-chip-k">{chip.k}</span>{chip.v}</span>
          ))}
          {/* The card's own acts, so he can walk the list with Next and act on each
              chart without closing it. Star and heart only where the host can save
              them (the screener grid); TradingView needs only the ticker. */}
          {onToggleWatchlist && (
            <button
              type="button"
              className="btn btn-icon btn-sm lens-toggle"
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
              className="btn btn-icon btn-sm lens-toggle"
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
            className="btn btn-sm"
            href={tradingViewUrl(ticker)}
            target="_blank"
            rel="noopener noreferrer"
            aria-keyshortcuts="T"
            title={`Open ${ticker} on TradingView (T)`}
          >
            ↗ TV
          </a>
        </div>
      </div>
    </header>
  );
}

// The chart box's own toolbar: "fix the box" on the left, how to move the chart on the right. The
// Daily / Weekly / Monthly tabs left it on Fri 30/10/2026 (his word); a side pane's caption opens it big.
export function LensChartToolbar({ fixing = false, onToggleFix }) {
  return (
    <div className="lens-chart-toolbar">
      <div className="lens-chart-toolbar-side">
        {/* "Fix the box" (Fri 17/10/2026): he corrects the reader's two lines on the daily chart; the fix is
            saved beside the reader's pair, the material the chooser is learned from later. Drawn only where
            the daily is a alpha read (the host hands in the toggle). */}
        {onToggleFix && (
          <button
            type="button"
            className="btn btn-sm lens-toggle"
            aria-pressed={Boolean(fixing)}
            aria-label="Fix the box"
            aria-keyshortcuts="B"
            title={fixing ? 'Back to the chart (B)' : 'Fix the box: open the fix page over this chart (B)'}
            onClick={onToggleFix}
          >
            ✎ {fixing ? 'fixing the box' : 'Fix the box'}
          </button>
        )}
      </div>
      <div className="lens-chart-toolbar-side">
        <span className="lens-chart-hint">wheel zooms · drag pans · ⌂ opening view</span>
      </div>
    </div>
  );
}
