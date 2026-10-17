import React, { useEffect, useRef, useState } from 'react';
import ScreenerStockLens from './ScreenerStockLens';
import SetupStoryPanel from './SetupStoryPanel';
import { buildPhaseRegions } from '../charts/chartPhaseOverlay';
import ChartZoomControls from '../charts/ChartZoomControls';
import TimeframeMainChart from '../charts/TimeframeMainChart';
import useDailyStructureChart from '../charts/useDailyStructureChart';
import ScreenerModalToolbar from './ScreenerModalToolbar';
import { hasFundamentalsSheet } from './fundamentalsSheetRead';
import { lensKeyAction } from './lensActions';
import { htfStateLabel } from './screenerCardData';

// The lens's skin (Thu 16/10/2026): 'dark' (the app's own colors, lifted inside the lens: the default he kept)
// or 'paper' (a light page, white blocks, a white chart) behind the toolbar's sun/moon button. Kept per
// browser. Every read of storage is guarded: it can be absent or throw.
const SKIN_KEY = 'chrollo.lensSkin';
const readSkin = () => {
  try {
    return localStorage.getItem(SKIN_KEY) === 'paper' ? 'paper' : 'dark';
  } catch {
    return 'dark';
  }
};

// THE THREE PANES (Fri 17/10/2026, his TradingView layout): the monthly over the weekly in a side
// column, the daily big beside them. The toolbar's D/W/M tab says which one is big; the other two
// take the side column, higher timeframe first; a click on a side pane's caption swaps it in.
const PANES = ['M', 'W', 'D'];
const PANE_NAME = { D: 'Daily', W: 'Weekly', M: 'Monthly' };
const SIDE_BARS = { W: 100, M: 60 };

const paneState = (data, tf) => {
  if (tf === 'W') {
    return htfStateLabel({
      stage2: data.htf_w_stage2, trendState: data.htf_w_trend_state,
      inConsol: data.htf_w_in_consol, phase: data.htf_w_phase, reaccum: data.htf_w_reaccum,
    });
  }
  if (tf === 'M') {
    return htfStateLabel({
      stage2: data.htf_m_stage2, trendState: data.htf_m_trend_state,
      inConsol: data.htf_m_in_consol, phase: data.htf_m_phase, reaccum: data.htf_m_reaccum,
    });
  }
  return null;
};

// One pane of the grid: a caption strip (the timeframe, its posture; a button on a side pane that
// opens it big) over the canvas the caller hands in.
function LensChartPane({ tf, big, data, onOpen, children }) {
  const state = paneState(data, tf);
  const caption = (
    <>
      <span className="lens-pane-name">{PANE_NAME[tf]}</span>
      {state ? <span className="lens-pane-state" style={{ color: state.tone }}>{state.label}</span> : null}
      {!big ? <span className="lens-pane-open" aria-hidden="true">open big ⤢</span> : null}
    </>
  );
  return (
    <div className={`lens-chart-pane ${big ? 'is-big' : 'is-side'}`} data-tf={tf}>
      {big ? (
        <div className="lens-pane-caption">{caption}</div>
      ) : (
        <button type="button" className="lens-pane-caption is-button" title={`Show the ${PANE_NAME[tf].toLowerCase()} in the big pane`} onClick={onOpen}>
          {caption}
        </button>
      )}
      <div className="lens-pane-canvas">{children}</div>
    </div>
  );
}

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
  // The panel under the chart has two pages (Tue 13/10/2026, his "show the fundamental card as a second page rather
  // then another block below"): the read, and the fundamentals when the scan carried a sheet.
  const [page, setPage] = useState('read');
  const hasSheet = hasFundamentalsSheet(data);
  const [skin, setSkin] = useState(readSkin);
  const toggleSkin = () => {
    const next = skin === 'paper' ? 'dark' : 'paper';
    setSkin(next);
    try {
      localStorage.setItem(SKIN_KEY, next);
    } catch {
      /* a browser that refuses storage still flips the skin for this lens */
    }
  };

  const hasWeekly = data?.weekly_candles?.length > 0;
  const hasMonthly = data?.monthly_candles?.length > 0;

  // Reset overlays and snap back to the daily chart and the read on every ticker change.
  useEffect(() => {
    setActiveRegion(null);
    selectInterval('D');
    setPage('read');
  }, [ticker]);

  // F flips the page, as it flips a card; only where there is a second page to flip to.
  useEffect(() => {
    if (!hasSheet) return undefined;
    const onKey = (event) => {
      if (lensKeyAction(event) !== 'fundamentals') return;
      event.preventDefault();
      setPage((now) => (now === 'read' ? 'fundamentals' : 'read'));
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [hasSheet]);

  // Escape closes the lens from every mount (not all parents wire it).
  useEffect(() => {
    const onKey = (event) => { if (event.key === 'Escape') onClose?.(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  // The daily is drawn wherever its pane sits (big, or in the side column): the slot word rebuilds it there.
  const daily = useDailyStructureChart(chartContainerRef, ticker, data, activeRegion, interval === 'D' ? 'main' : 'side', skin);

  const paneCanvas = (tf, big) => {
    if (tf === 'D') {
      return (
        <div className="lens-daily-frame">
          <div ref={chartContainerRef} className="lens-daily-canvas" />
          <ChartZoomControls chartRef={daily.chartRef} onHome={daily.home} />
        </div>
      );
    }
    return (
      <TimeframeMainChart
        bars={big ? null : SIDE_BARS[tf]}
        box={tf === 'W' ? data.weekly_box : data.monthly_box}
        candles={tf === 'W' ? data.weekly_candles : data.monthly_candles}
        label={tf === 'W' ? 'WEEKLY' : 'MONTHLY'}
        volumes={tf === 'W' ? data.weekly_volumes : data.monthly_volumes}
      />
    );
  };

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
        data-skin={skin}
        style={{
          // The shell fills the screen's height and its body SCROLLS: the chart
          // block at its own height, then the stats block at its natural height
          // (operator, Thu 16/10/2026: "One block for the chart. and another
          // block for the Stats ... I can scroll the page so the space is
          // essentially infinite"). 1760 is the 1920 screen's width.
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
          skin={skin}
          onToggleSkin={toggleSkin}
          ticker={ticker}
          watchlisted={watchlisted}
        />
        {/* THE LENS IS TWO BLOCKS (operator, Fri 17/10/2026): the CHART block — the three panes laid out
            as his TradingView (monthly over weekly in a side column, the daily big) with the grade board,
            the phases over their events, right under them in the SAME card, so the chart and the
            highlights it lights sit in one screen — and the STATS block under it, at its natural height;
            the body scrolls to it. */}
        <div className="screener-modal-body lens-page" style={{ display: 'flex', flex: 1, flexDirection: 'column', minHeight: 0, overflowY: 'auto' }}>
          <section key={skin} className="lens-block lens-block-chart">
            <header className="lens-block-head">
              <span>Chart</span>
              <small>the daily big, the monthly and the weekly beside it; the wheel over a pane zooms it, drag the bars to pan, ⌂ back to the opening view, ⤢ the whole history; click a small pane to open it big</small>
            </header>
            <div className="lens-card">
              <div className="lens-chart-grid" style={{ flex: '0 0 auto' }}>
                <div className="lens-chart-side">
                  {PANES.filter((tf) => tf !== interval).map((tf) => (
                    <LensChartPane big={false} data={data} key={tf} onOpen={() => selectInterval(tf)} tf={tf}>
                      {paneCanvas(tf, false)}
                    </LensChartPane>
                  ))}
                </div>
                <div className="lens-chart-main">
                  <LensChartPane big data={data} tf={interval}>
                    {paneCanvas(interval, true)}
                  </LensChartPane>
                </div>
              </div>
              <SetupStoryPanel
                data={data}
                note={null}
                onRegionChange={setActiveRegion}
                regions={buildPhaseRegions(data)}
              />
            </div>
          </section>
          <section className="lens-block lens-block-stats">
            <header className="lens-block-head">
              <span>The stock</span>
              <small>the technical read, leadership, volume at the key points, and the fundamentals page</small>
            </header>
            <div className="lens-card">
              <ScreenerStockLens
                activeRegion={activeRegion}
                data={data}
                earnings={earnings}
                interval={interval}
                onPageChange={hasSheet ? setPage : null}
                onRegionChange={setActiveRegion}
                page={hasSheet ? page : 'read'}
                scanIdentity={scanIdentity}
                story={false}
                ticker={ticker}
              />
            </div>
          </section>
        </div>
        {footer}
      </section>
    </div>
  );
};

export default ScreenerModal;
