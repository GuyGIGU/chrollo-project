import { useEffect, useMemo, useRef } from 'react';
import { createSeriesMarkers } from 'lightweight-charts';
import useLightweightChart from './useLightweightChart';
import { attachPhaseOverlay, colorLpsCandles, rootSwingRange } from '../components/chartPhaseOverlay';
import { CHART_FRAMING, finiteNumber, modalFocusLogicalRange } from '../components/chartGeometry';
import { addBoxRails } from '../components/chartRails';
import { baseChartOptions, CHART_COLORS } from '../components/chartTheme';

const chartOptions = (width, height) => {
  const base = baseChartOptions('modal', width, height);
  return {
    ...base,
    crosshair: { mode: 1 },
    // Tight vertical fit so amplitude isn't flattened; bottom band sized to the
    // (now smaller) volume footprint so price/volume don't overlap.
    rightPriceScale: { ...base.rightPriceScale, scaleMargins: CHART_FRAMING.modal.scaleMargins, autoScale: true },
    timeScale: { ...base.timeScale, timeVisible: true, fixLeftEdge: false, fixRightEdge: false },
    handleScroll: true,
    handleScale: true,
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
const setFocusedRange = (chart, data) => {
  const range = modalFocusLogicalRange(data);
  if (!range) return;
  chart.timeScale().setVisibleRange({
    from: data.candles[range.from].time,
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
export default function useDailyStructureChart(containerRef, ticker, data, activePhaseRegion = null, interval = 'D') {
  const activeRegionRef = useRef(activePhaseRegion);
  const phaseOverlayRef = useRef(null);

  useEffect(() => {
    activeRegionRef.current = activePhaseRegion;
    phaseOverlayRef.current?.setActiveRegion(activePhaseRegion);
  }, [activePhaseRegion]);

  // Only the daily timeframe uses this rich structure-overlay chart; the
  // weekly/monthly tabs render TimeframeMainChart instead. Guarding on interval
  // (via candles passed to the hook) keeps returning to Daily re-init cleanly.
  const dailyCandles = interval === 'D' ? data?.candles : null;
  // Memoized on the chart's own deps: the glyph-tape hover re-renders the
  // whole modal per mouse transition, and unmemoized this deep-cloned the
  // full candle array every time just to throw it away (council review
  // 2026-08-05, finding 13 — ~24 clone-and-discard renders per tape sweep).
  const coloredCandles = useMemo(
    () => (dailyCandles?.length ? colorStructureCandles(data) : null),
    [data, dailyCandles],
  );

  useLightweightChart(containerRef, {
    chartOptions: (container) => chartOptions(container.clientWidth, container.clientHeight),
    candles: coloredCandles,
    barOptions: { upColor: CHART_COLORS.candle, downColor: CHART_COLORS.candle, thinBars: false },
    volumes: data?.volumes,
    showVolume: true,
    volumeScaleTop: CHART_FRAMING.modal.volumeScaleTop,
    showSma: true,
    onReady: (chart, candleSeries) => {
      const phaseOverlay = attachPhaseOverlay({
        activeRegion: activeRegionRef.current,
        candleSeries,
        chart,
        container: containerRef.current,
        data,
      });
      phaseOverlayRef.current = phaseOverlay;
      // The SAME rail drawer the mini card uses — card and modal cannot diverge.
      addBoxRails(chart, data);
      addAnnotations(candleSeries, data.annotations || {});
      setFocusedRange(chart, data);

      return () => {
        phaseOverlay.remove();
        if (phaseOverlayRef.current === phaseOverlay) phaseOverlayRef.current = null;
      };
    },
    onResize: (chart, container) =>
      chart.applyOptions({ width: container.clientWidth, height: container.clientHeight }),
    resizeDelayMs: 100,
    deps: [containerRef, data, ticker, interval],
  });
}
