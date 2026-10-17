import { useEffect, useMemo, useRef } from 'react';
import { createSeriesMarkers, createTextWatermark } from 'lightweight-charts';
import useLightweightChart from './useLightweightChart';
import { attachPhaseOverlay, colorLpsCandles, rootSwingRange } from './chartPhaseOverlay';
import { CHART_FRAMING, finiteNumber, modalFocusLogicalRange } from './chartGeometry';
import { addBoxRails } from './chartRails';
import { baseChartOptions, CHART_COLORS, lensBarOptions, lensSmaOptions } from './chartTheme';

// The month columns a shade stronger than the horizontal grid, so they read as columns, not noise.
const skinGrid = (base) => base.grid?.horzLines?.color ?? 'rgba(98, 110, 140, 0.16)';

const chartOptions = (width, height, container) => {
  const base = baseChartOptions('modal', width, height, container);
  return {
    ...base,
    // ResizeObserver-backed, like the card and calibration charts: the pane
    // follows its CONTAINER, so a UI-scale change or a move to the other
    // monitor — neither fires a window resize — re-fits it (review 2026-10-02;
    // it used to keep its old width until the window itself was resized).
    autoSize: true,
    crosshair: { mode: 1 },
    // Tight vertical fit so amplitude isn't flattened; bottom band sized to the
    // (now smaller) volume footprint so price/volume don't overlap.
    rightPriceScale: { ...base.rightPriceScale, scaleMargins: CHART_FRAMING.modal.scaleMargins, autoScale: true },
    // The lens's chart (Thu 16/10/2026): the vertical grid at the MONTHS only (a tick mark's label budget of 22
    // characters starves the day marks, so only month and year marks are admitted and the grid, which follows
    // the marks, draws one column per month like MarketSmith's), the pane separator a hairline.
    grid: { ...base.grid, vertLines: { color: skinGrid(base), visible: true } },
    layout: { ...base.layout, panes: { separatorColor: base.timeScale?.borderColor, separatorHoverColor: 'rgba(79,207,196,0.18)', enableResize: false } },
    // lockVisibleTimeRangeOnResize: a resize (the window dragged to the other
    // monitor, the UI scale stepped — autoSize sees both) keeps the FRAMED
    // trading days and re-spaces the bars, instead of keeping the bar spacing
    // and silently showing more or fewer days than modalFocusLogicalRange chose
    // (2026-10-02).
    timeScale: { ...base.timeScale, timeVisible: true, fixLeftEdge: false, fixRightEdge: false,
                 lockVisibleTimeRangeOnResize: true, tickMarkMaxCharacterLength: 22, allowBoldLabels: false },
    // The wheel over a pane ZOOMS it, as on TradingView (Fri 17/10/2026, his nit: "if the mouse is in
    // the chart it works so i can zoom and drag without having to hold CNTRL"); the lens page scrolls
    // from outside the panes. A sideways wheel pans; the axis drags scale; a double click resets.
    handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
    handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true, axisDoubleClickReset: true },
  };
};

// --- structure candle coloring (modal): root-swing (the r/s anchor pair the box's
// rails are drawn from) grey, LPS zones painted by the shared chronological gradient.
// BOTH read the shared chartPhaseOverlay helpers (rootSwingRange / colorLpsCandles),
// so the card and modal colour the identical bars by construction. ---
const colorStructureCandles = (data) => {
  const candles = JSON.parse(JSON.stringify(data.candles || []));
  if (data.base_len <= 0) return candles;

  colorBase(candles, data);
  colorLpsCandles(candles, data, CHART_COLORS.gold);
  return candles;
};

// Grey the ROOT SWING bars (the r/s anchor pair the box's rails are drawn from) via
// the SAME shared span the mini card uses, so card and modal never diverge.
const colorBase = (candles, data) => {
  const rootSwing = rootSwingRange(data, candles);
  if (!rootSwing) return;
  for (let index = rootSwing.startIndex; index <= rootSwing.endIndex; index += 1) {
    if (index >= 0 && index < candles.length) candles[index].color = CHART_COLORS.baseLimb;
  }
};

const addAnnotations = (candleSeries, annotations) => {
  if (annotations.trigger_price) {
    candleSeries.createPriceLine({
      price: annotations.trigger_price,
      color: CHART_COLORS.gold,
      lineWidth: 1,
      lineStyle: 2,
      axisLabelVisible: true,
      title: 'Trigger',
    });
  }

  const markers = buildMarkers(annotations);
  if (markers.length > 0) {
    markers.sort((a, b) => a.time.localeCompare(b.time));
    createSeriesMarkers(candleSeries, markers);
  }
};

const buildMarkers = (annotations) => {
  const markers = [];
  if (annotations.trigger_date) {
    markers.push({ time: annotations.trigger_date, position: 'belowBar', color: CHART_COLORS.success, shape: 'arrowUp', text: 'TRIG' });
  }
  const mfe20d = finiteNumber(annotations.mfe_20d);
  const mae20d = finiteNumber(annotations.mae_20d);
  if (annotations.mfe_20d_date && mfe20d != null) {
    markers.push({ time: annotations.mfe_20d_date, position: 'aboveBar', color: CHART_COLORS.success, shape: 'circle', text: `MFE ${(mfe20d * 100).toFixed(1)}%` });
  }
  if (annotations.mae_20d_date && mae20d != null) {
    markers.push({ time: annotations.mae_20d_date, position: 'belowBar', color: '#c76b73', shape: 'circle', text: `MAE ${(mae20d * 100).toFixed(1)}%` });
  }
  return markers;
};

// The window itself is pure math shared with the mini card (chartGeometry); this
// only maps the resolved logical range onto the time axis the modal scrolls in.
// In a NARROW pane (the lens's side column, when the daily is the small one of
// the three, Fri 17/10/2026) the same span would be ~3 px/bar: it shows the
// newest SIDE_PANE_BARS instead, the right edge where it is.
const SIDE_PANE_BARS = 80;
const NARROW_PANE_PX = 700;
const setFocusedRange = (chart, data, container) => {
  const range = modalFocusLogicalRange(data);
  if (!range) return;
  const narrow = container && container.clientWidth > 0 && container.clientWidth < NARROW_PANE_PX;
  const from = narrow ? Math.max(range.from, range.to - SIDE_PANE_BARS + 1) : range.from;
  chart.timeScale().setVisibleRange({
    from: data.candles[from].time,
    to: data.candles[range.to].time,
  });
};

// The big interactive DAILY structure chart — rails, phase regions, LPS
// coloring, focus window — consumed by BOTH the Screener modal and the
// Watchlist page's Daily pane (renamed from useScreenerModalChart when it
// gained its second surface). `data` is consumed atomically: a full scan-row
// payload draws the whole read; a candles-only payload (the Watchlist clean
// chart) renders bare price/volume because every overlay helper no-ops on
// absent fields. The 'modal' theme-profile key below is a styling profile
// name, not a surface claim.
// `skin` is the lens's skin word (null outside the lens): it rides the deps so a skin flip redraws the canvas.
// `slot` is a word for WHERE the lens seats the daily (the big pane or the side column, Fri 17/10/2026): it
// rides the deps so the chart is rebuilt in the pane's new element when the panes swap.
// Returns a handle for the zoom controls: the live chart (null between builds) and `home`, the opening view.
// `clickRef` (optional) is a ref whose current value is a handler for a click on a bar, {date, price, bar},
// or null: the lens's "fix the box" (Fri 17/10/2026) sets it while armed. Subscribed once per build and read
// through the ref, so arming never rebuilds the chart.
export default function useDailyStructureChart(containerRef, ticker, data, activePhaseRegion = null, slot = 'main', skin = null, clickRef = null) {
  const activeRegionRef = useRef(activePhaseRegion);
  const phaseOverlayRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    activeRegionRef.current = activePhaseRegion;
    phaseOverlayRef.current?.setActiveRegion(activePhaseRegion);
  }, [activePhaseRegion]);

  const dailyCandles = data?.candles;
  // Memoized on the chart's own deps: the glyph-tape hover re-renders the
  // whole modal per mouse transition, and unmemoized this deep-cloned the
  // full candle array every time just to throw it away (council review
  // 2026-08-05, finding 13 — ~24 clone-and-discard renders per tape sweep).
  const coloredCandles = useMemo(
    () => (dailyCandles?.length ? colorStructureCandles(data) : null),
    [data, dailyCandles],
  );

  useLightweightChart(containerRef, {
    chartOptions: (container) => chartOptions(container.clientWidth, container.clientHeight, container),
    candles: coloredCandles,
    barOptions: lensBarOptions,
    smaOptions: lensSmaOptions,
    volumes: data?.volumes,
    showVolume: true,
    volumePane: CHART_FRAMING.modal.volumePane,
    volumeScaleTop: CHART_FRAMING.modal.volumeScaleTop,
    showSma: true,
    onReady: (chart, candleSeries) => {
      chartRef.current = chart;
      const phaseOverlay = attachPhaseOverlay({
        activeRegion: activeRegionRef.current,
        candleSeries,
        chart,
        container: containerRef.current,
        data,
      });
      phaseOverlayRef.current = phaseOverlay;
      // The ticker as a faint watermark on the price pane and the word on the volume pane (Thu 16/10/2026):
      // the panes name themselves, as on MarketSmith and TradingView.
      try {
        const panes = chart.panes();
        const ink = { color: 'rgba(128, 140, 170, 0.10)', fontFamily: "'JetBrains Mono', monospace", fontStyle: 'bold' };
        if (panes[0] && ticker) createTextWatermark(panes[0], { horzAlign: 'left', vertAlign: 'top', lines: [{ ...ink, text: ticker, fontSize: 44 }] });
        if (panes[1]) createTextWatermark(panes[1], { horzAlign: 'left', vertAlign: 'top', lines: [{ ...ink, text: 'VOLUME', fontSize: 12 }] });
      } catch {
        /* a watermark is decoration: never let it cost the chart */
      }
      // The SAME rail drawer the mini card uses — card and modal cannot diverge.
      addBoxRails(chart, data);
      addAnnotations(candleSeries, data.annotations || {});
      setFocusedRange(chart, data, containerRef.current);
      const barsByDate = new Map((data.candles || []).map((candle) => [candle.time, candle]));
      const onClick = (param) => {
        const handler = clickRef?.current;
        if (!handler || !param?.point || param.time == null) return;
        const date = typeof param.time === 'string' ? param.time : null;
        const price = candleSeries.coordinateToPrice(param.point.y);
        if (!date || price == null || !Number.isFinite(price)) return;
        handler({ date, price, bar: barsByDate.get(date) || null });
      };
      chart.subscribeClick(onClick);

      return () => {
        try { chart.unsubscribeClick(onClick); } catch { /* the chart may already be gone */ }
        phaseOverlay.remove();
        if (phaseOverlayRef.current === phaseOverlay) phaseOverlayRef.current = null;
        if (chartRef.current === chart) chartRef.current = null;
      };
    },
    deps: [containerRef, data, ticker, slot, skin],
  });

  return {
    chartRef,
    home: () => { if (chartRef.current) setFocusedRange(chartRef.current, data, containerRef.current); },
  };
}
