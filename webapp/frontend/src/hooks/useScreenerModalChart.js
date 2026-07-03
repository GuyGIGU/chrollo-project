import { useEffect, useRef } from 'react';
import { createSeriesMarkers } from 'lightweight-charts';
import useLightweightChart from './useLightweightChart';
import { attachPhaseOverlay, buildPhaseRegions } from '../components/chartPhaseOverlay';
import { finiteNumber } from '../components/chartGeometry';
import { addBoxRails } from '../components/chartRails';
import { baseChartOptions, CHART_COLORS } from '../components/chartTheme';

const chartOptions = (width, height) => {
  const base = baseChartOptions('modal', width, height);
  return {
    ...base,
    crosshair: { mode: 1 },
    // Tight vertical fit so amplitude isn't flattened; bottom band sized to the
    // (now smaller) volume footprint so price/volume don't overlap.
    rightPriceScale: { ...base.rightPriceScale, scaleMargins: { top: 0.06, bottom: 0.16 }, autoScale: true },
    timeScale: { ...base.timeScale, timeVisible: true, fixLeftEdge: false, fixRightEdge: false },
    handleScroll: true,
    handleScale: true,
  };
};

// --- structure candle coloring (modal variant: r/s anchors grey, LPS regions
// from buildPhaseRegions gold). Lives here because it depends on the DOM-coupled
// chartPhaseOverlay module; chartGeometry stays pure/Node-testable. ---
const colorStructureCandles = (data, baseEnd) => {
  const candles = JSON.parse(JSON.stringify(data.candles || []));
  if (data.base_len <= 0) return candles;

  const baseStart = Math.max(0, baseEnd - data.base_len + 1);
  colorBase(candles, data, baseStart, baseEnd);
  colorLps(candles, data, baseEnd);
  return candles;
};

const colorBase = (candles, data, baseStart, baseEnd) => {
  if (data.r_anchor == null || data.s_anchor == null) {
    for (let index = baseStart; index <= baseEnd; index += 1) {
      if (index >= 0 && index < candles.length) candles[index].color = CHART_COLORS.baseLimb;
    }
    return;
  }

  const rawBaseStart = baseEnd - data.base_len + 1;
  const rBar = rawBaseStart + data.r_anchor;
  const sBar = rawBaseStart + data.s_anchor;
  // rawBaseStart in the min: the shared-rail back-extension can open the box
  // before the anchor pair; the base coloring must still cover its left edge.
  for (let index = Math.min(rBar, sBar, rawBaseStart); index <= Math.max(rBar, sBar); index += 1) {
    if (index >= 0 && index < candles.length) candles[index].color = CHART_COLORS.baseLimb;
  }
};

const colorLps = (candles, data, baseEnd) => {
  let colored = false;
  const lpsRegions = buildPhaseRegions(data).filter(region => region.key === 'lps');
  for (const region of lpsRegions) {
    for (let index = region.startIndex; index <= region.endIndex; index += 1) {
      if (index >= 0 && index < candles.length) {
        candles[index].color = region.color || CHART_COLORS.gold;
        colored = true;
      }
    }
  }

  if (colored) return;
  if (data.lps_len <= 0 || data.lps_offset === undefined) return;
  const lpsEnd = baseEnd - data.lps_offset;
  const lpsStart = Math.max(0, lpsEnd - data.lps_len + 1);
  for (let index = lpsStart; index <= lpsEnd; index += 1) {
    if (index >= 0 && index < candles.length) candles[index].color = CHART_COLORS.gold;
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

const setFocusedRange = (chart, data, baseEnd) => {
  if (!data.candles?.length) return;
  // Show the base with substantial pre-base trend context (~120-160 bars) so it
  // renders at a faithful daily density (~9-12px/bar in the wide modal pane)
  // instead of ~52 bars stretched to ~20-28px/bar, which flattened the base.
  const displayStart = Math.max(0, baseEnd - Math.max(data.base_len + 90, 120));
  chart.timeScale().setVisibleRange({
    from: data.candles[displayStart].time,
    to: data.candles[data.candles.length - 1].time,
  });
};

export default function useScreenerModalChart(containerRef, ticker, data, activePhaseRegion = null, interval = 'D') {
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
  const forwardBars = data?.forward_bars || 0;
  const baseEnd = (data?.candles?.length || 0) - 1 - forwardBars;
  const coloredCandles = dailyCandles?.length ? colorStructureCandles(data, baseEnd) : null;

  useLightweightChart(containerRef, {
    chartOptions: (container) => chartOptions(container.clientWidth, container.clientHeight),
    candles: coloredCandles,
    barOptions: { upColor: CHART_COLORS.candle, downColor: CHART_COLORS.candle, thinBars: false },
    volumes: data?.volumes,
    showVolume: true,
    volumeScaleTop: 0.84,
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
      setFocusedRange(chart, data, baseEnd);

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
