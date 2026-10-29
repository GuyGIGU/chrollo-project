import React, { useEffect, useRef, useState } from 'react';
import ScreenerStockLens, { LensPageTabs } from './ScreenerStockLens';
import SetupStoryPanel from './SetupStoryPanel';
import { buildPhaseRegions } from '../charts/chartPhaseOverlay';
import ChartZoomControls from '../charts/ChartZoomControls';
import TimeframeMainChart from '../charts/TimeframeMainChart';
import useDailyStructureChart from '../charts/useDailyStructureChart';
import { LensChartToolbar, LensNavBar, LensQuote } from './ScreenerModalToolbar';
import { hasFundamentalsSheet } from './fundamentalsSheetRead';
import BoxFixPage from './BoxFixPage';
import { lensKeyAction } from './lensActions';
import useFixedBox from './useFixedBox';
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
// column, the big pane beside them. The toolbar's Daily / Weekly / Monthly says which one is big; the
// other two take the side column, higher timeframe first; a click on a side pane's caption swaps it in.
// One Finviz chart replaced them on Thu 29/10/2026 and he had them back the same day ("I still need the
// 3 sized screen of Daily/weekly/monthly").
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

  // The daily is drawn wherever its pane sits (big, or in the side column): the slot word rebuilds it there.
  const daily = useDailyStructureChart(chartContainerRef, ticker, data, activeRegion, interval === 'D' ? 'main' : 'side', skin);
  // "Fix the box" (Fri 17/10/2026; the page Sat 18/10/2026): the toolbar's button (or B) covers the lens with the
  // fix page; the fix saved before is drawn on this chart in the operator colour and named in the toolbar.
  const [fixing, setFixing] = useState(false);
  const fixingRef = useRef(false);
  fixingRef.current = fixing;
  const canFix = Boolean(data?.two_eyes) && (data?.candles?.length ?? 0) > 0;
  const fixedBox = useFixedBox(ticker, data, daily.chartRef);
  useEffect(() => { setFixing(false); }, [ticker]);

  // F flips the page, as it flips a card; only where there is a second page to flip to.
  useEffect(() => {
    if (!hasSheet) return undefined;
    const onKey = (event) => {
      if (fixingRef.current || lensKeyAction(event) !== 'fundamentals') return;
      event.preventDefault();
      setPage((now) => (now === 'read' ? 'fundamentals' : 'read'));
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [hasSheet]);

  // Escape closes the lens from every mount (not all parents wire it); while the fix page is up it is the page's.
  useEffect(() => {
    const onKey = (event) => {
      if (fixingRef.current) return;
      if (event.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

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
  const onToggleFix = canFix ? () => setFixing((now) => !now) : undefined;
  const fundamentalsShown = hasSheet && page === 'fundamentals';
  const pageTabs = hasSheet ? <LensPageTabs onPageChange={setPage} page={page} /> : null;

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
          // essentially infinite"). 1896 is the WHOLE 1920 screen inside the
          // scrim's 12px frame (his "make the entire pop up bigger", Thu
          // 29/10/2026; 1760 until then), and the cap holds that size on the
          // 2560 screen: "retain the original size ... same goes for the big
          // charts" (2026-10-03). A bigger screen shows more page around it.
          background: 'var(--bg-main)',
          border: '1px solid var(--border-color)',
          borderRadius: 8,
          boxShadow: '0 22px 55px rgba(0,0,0,0.45)',
          display: 'flex',
          flex: 1,
          flexDirection: 'column',
          margin: '0 auto',
          maxWidth: 1896,
          minHeight: 0,
          overflow: 'hidden',
          position: 'relative',
        }}
        onClick={event => event.stopPropagation()}
      >
        <LensNavBar
          backLabel="Back"
          onClose={onClose}
          onNext={onNext}
          onPrev={onPrev}
          onToggleFix={onToggleFix}
          onToggleLike={onToggleLike}
          onToggleSkin={toggleSkin}
          onToggleWatchlist={onToggleWatchlist}
          position={position}
          skin={skin}
          ticker={ticker}
        />
        {/* The fix page covers the lens (Sat 18/10/2026, "a new page covers this one"); Save or Back returns here. */}
        {fixing && (
          <BoxFixPage
            data={data}
            fixed={fixedBox.fixed}
            onClose={() => setFixing(false)}
            onSaved={(fix) => { fixedBox.setFixed(fix); setFixing(false); }}
            scanIdentity={scanIdentity}
            skin={skin}
            ticker={ticker}
          />
        )}
        {/* THE LENS IS FINVIZ'S QUOTE PAGE (Thu 29/10/2026): the quote, the chart box (its toolbar, the three panes),
            then the grade board and the stock's numbers, compact, one column; the body scrolls. The Fundamentals
            tab swaps the board and the numbers for the sheet and keeps the chart. */}
        <div className="screener-modal-body lens-page" style={{ display: 'flex', flex: 1, flexDirection: 'column', minHeight: 0, overflowY: 'auto' }}>
          <LensQuote
            data={data}
            fixedSummary={fixedBox.fixed?.summary ?? null}
            liked={liked}
            onToggleLike={onToggleLike}
            onToggleWatchlist={onToggleWatchlist}
            tabs={pageTabs}
            ticker={ticker}
            watchlisted={watchlisted}
          />
          <section key={skin} className="lens-chart-box">
            <LensChartToolbar
              fixing={fixing}
              hasMonthly={hasMonthly}
              hasWeekly={hasWeekly}
              interval={interval}
              onIntervalChange={selectInterval}
              onToggleFix={onToggleFix}
            />
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
          </section>
          {!fundamentalsShown && (
            <section className="lens-box">
              <SetupStoryPanel
                data={data}
                note={null}
                onRegionChange={setActiveRegion}
                regions={buildPhaseRegions(data)}
              />
            </section>
          )}
          <ScreenerStockLens
            activeRegion={activeRegion}
            data={data}
            earnings={earnings}
            interval={interval}
            onRegionChange={setActiveRegion}
            page={fundamentalsShown ? 'fundamentals' : 'read'}
            scanIdentity={scanIdentity}
            story={false}
            ticker={ticker}
          />
        </div>
        {footer}
      </section>
    </div>
  );
};

export default ScreenerModal;
