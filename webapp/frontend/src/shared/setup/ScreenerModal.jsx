import React, { useEffect, useRef, useState } from 'react';
import ScreenerStockLens from './ScreenerStockLens';
import TimeframeMainChart from '../charts/TimeframeMainChart';
import TimeframeMiniRow from './TimeframeMiniRow';
import useDailyStructureChart from '../charts/useDailyStructureChart';
import ScreenerModalToolbar from './ScreenerModalToolbar';

// The top bar (ScreenerModalToolbar.jsx) draws the star, the heart and the
// "12 / 37" counter only when the host hands them in (the screener grid does);
// every other lens gets ↗ TV alone.
const ScreenerModal = ({
  ticker, data, earnings, scanIdentity = null, onClose, onPrev, onNext, footer = null,
  watchlisted = false, onToggleWatchlist, liked = false, onToggleLike, position = null,
}) => {
  const chartContainerRef = useRef(null);
  const [activeRegion, setActiveRegion] = useState(null);
  const [interval, selectInterval] = useState('D');

  const hasWeekly = data?.weekly_candles?.length > 0;
  const hasMonthly = data?.monthly_candles?.length > 0;

  // Reset overlays and snap back to the daily chart on every ticker change.
  useEffect(() => {
    setActiveRegion(null);
    selectInterval('D');
  }, [ticker]);

  useEffect(() => {
    if (interval !== 'D') setActiveRegion(null);
  }, [interval]);

  // Escape closes the lens from every mount (not all parents wire it).
  useEffect(() => {
    const onKey = (event) => { if (event.key === 'Escape') onClose?.(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  useDailyStructureChart(chartContainerRef, ticker, data, activeRegion, interval);

  return (
    <div
      style={{
        background: 'rgba(8, 10, 15, 0.92)',
        bottom: 0,
        display: 'flex',
        left: 0,
        // The scrim is a frame, not a margin: every px of padding here is a px
        // the charts don't get. 12 still reads as "floating over the page".
        padding: 12,
        position: 'fixed',
        right: 0,
        top: 0,
        zIndex: 5000,
      }}
      onClick={onClose}
    >
      <section
        className="screener-modal-shell"
        role="dialog"
        aria-modal="true"
        aria-label={`${ticker} chart lens`}
        style={{
          // The shell fills the screen's height; the CHART BAND inside it holds
          // its 1920 size (.screener-modal-chart-row, operator 2026-10-03) and
          // the read panel below takes every extra px — "make that block
          // stretch more down so we could see more, even put the entire big
          // chart higher". 1760 is the 1920 screen's width too.
          background: 'var(--bg-main)',
          border: '1px solid var(--border-color)',
          borderRadius: 8,
          boxShadow: '0 22px 55px rgba(0,0,0,0.45)',
          display: 'flex',
          flex: 1,
          flexDirection: 'column',
          margin: '0 auto',
          maxWidth: 1760,
          minHeight: 0,
          overflow: 'hidden',
        }}
        onClick={event => event.stopPropagation()}
      >
        <ScreenerModalToolbar
          data={data}
          hasMonthly={hasMonthly}
          hasWeekly={hasWeekly}
          interval={interval}
          liked={liked}
          onClose={onClose}
          onIntervalChange={selectInterval}
          onNext={onNext}
          onPrev={onPrev}
          onToggleLike={onToggleLike}
          onToggleWatchlist={onToggleWatchlist}
          position={position}
          ticker={ticker}
          watchlisted={watchlisted}
        />
        <div className="screener-modal-body" style={{ display: 'flex', flex: 1, flexDirection: 'column', minHeight: 0 }}>
          {/* Chart band: the W/M preview cubes as a LEFT side column, then the
              daily pane. The old full-width strip under the daily gave each
              preview a ~700x110 brick (indecipherable) while stretching the
              daily across the whole shell; the column makes the previews medium
              cubes and narrows the daily back toward the card's faithful
              density. Cubes lead (operator 2026-08-12) — the higher timeframe is
              the context you read BEFORE the daily, so it sits where reading
              starts. DOM order is visual order, so tab order follows too. */}
          <div className="screener-modal-chart-row" style={{ display: 'flex', flex: '0 0 auto', minHeight: 0 }}>
            {interval === 'D' && (
              <TimeframeMiniRow data={data} onSelectInterval={selectInterval} />
            )}
            <div className="screener-modal-chart-shell" style={{ flex: '1 1 auto', minHeight: 0, minWidth: 0, position: 'relative' }}>
              {interval === 'D' ? (
                <div ref={chartContainerRef} className="screener-modal-chart" style={{ height: '100%', minHeight: 0, position: 'relative' }} />
              ) : (
                <TimeframeMainChart
                  key={interval}
                  box={interval === 'W' ? data.weekly_box : data.monthly_box}
                  candles={interval === 'W' ? data.weekly_candles : data.monthly_candles}
                  label={interval === 'W' ? 'WEEKLY' : 'MONTHLY'}
                  volumes={interval === 'W' ? data.weekly_volumes : data.monthly_volumes}
                />
              )}
            </div>
          </div>
          <ScreenerStockLens
            activeRegion={activeRegion}
            data={data}
            earnings={earnings}
            interval={interval}
            onRegionChange={setActiveRegion}
            scanIdentity={scanIdentity}
            ticker={ticker}
          />
        </div>
        {footer}
      </section>
    </div>
  );
};

export default ScreenerModal;
