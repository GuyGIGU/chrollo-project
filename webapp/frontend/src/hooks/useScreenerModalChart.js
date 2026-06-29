import { useEffect, useRef } from 'react';
import { LineSeries, createSeriesMarkers } from 'lightweight-charts';
import useLightweightChart from './useLightweightChart';
import { attachPhaseOverlay, buildPhaseRegions } from '../components/chartPhaseOverlay';
import { buildLevelData, finiteNumber } from '../components/chartGeometry';

const chartOptions = (width, height) => ({
  width,
  height,
  layout: {
    background: { type: 'solid', color: '#171922' },
    textColor: '#8b949e',
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 12,
  },
  grid: {
    vertLines: { color: 'rgba(70, 77, 98, 0.18)' },
    horzLines: { color: 'rgba(70, 77, 98, 0.18)' },
  },
  crosshair: { mode: 1 },
  rightPriceScale: {
    borderColor: '#2f3447',
    scaleMargins: { top: 0.08, bottom: 0.22 },
  },
  timeScale: {
    borderColor: '#2f3447',
    timeVisible: true,
    fixLeftEdge: false,
    fixRightEdge: false,
  },
  handleScroll: true,
  handleScale: true,
});

const levelOptions = {
  color: '#2457b8',
  lineWidth: 2,
  crosshairMarkerVisible: false,
  lastValueVisible: false,
  priceLineVisible: false,
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
      if (index >= 0 && index < candles.length) candles[index].color = '#5d6474';
    }
    return;
  }

  const rawBaseStart = baseEnd - data.base_len + 1;
  const rBar = rawBaseStart + data.r_anchor;
  const sBar = rawBaseStart + data.s_anchor;
  for (let index = Math.min(rBar, sBar); index <= Math.max(rBar, sBar); index += 1) {
    if (index >= 0 && index < candles.length) candles[index].color = '#5d6474';
  }
};

const colorLps = (candles, data, baseEnd) => {
  let colored = false;
  const lpsRegions = buildPhaseRegions(data).filter(region => region.key === 'lps');
  for (const region of lpsRegions) {
    for (let index = region.startIndex; index <= region.endIndex; index += 1) {
      if (index >= 0 && index < candles.length) {
        candles[index].color = region.color || '#e3b341';
        colored = true;
      }
    }
  }

  if (colored) return;
  if (data.lps_len <= 0 || data.lps_offset === undefined) return;
  const lpsEnd = baseEnd - data.lps_offset;
  const lpsStart = Math.max(0, lpsEnd - data.lps_len + 1);
  for (let index = lpsStart; index <= lpsEnd; index += 1) {
    if (index >= 0 && index < candles.length) candles[index].color = '#e3b341';
  }
};

const addStructureLevels = (chart, data, baseEnd) => {
  const startIndex = Math.max(0, baseEnd - data.base_len + 1);
  const midValue = (Number(data.R) + Number(data.S)) / 2;

  chart.addSeries(LineSeries, levelOptions).setData(buildLevelData(data.candles || [], startIndex, data.R));
  chart.addSeries(LineSeries, levelOptions).setData(buildLevelData(data.candles || [], startIndex, data.S));
  chart.addSeries(LineSeries, {
    ...levelOptions,
    color: 'rgba(139, 148, 158, 0.45)',
    lineWidth: 1,
    lineStyle: 2,
  }).setData(buildLevelData(data.candles || [], startIndex, midValue));

  const innerR = finiteNumber(data.inner_R);
  const innerS = finiteNumber(data.inner_S);
  const innerStartBar = finiteNumber(data.inner_start_bar);
  if (innerR != null && innerS != null && innerStartBar != null) {
    const innerStart = Math.max(0, Math.min((data.candles || []).length - 1, Math.trunc(innerStartBar)));
    const innerOptions = {
      ...levelOptions,
      color: '#5f8fe6',
      lineWidth: 2,
    };
    chart.addSeries(LineSeries, innerOptions).setData(buildLevelData(data.candles || [], innerStart, innerR));
    chart.addSeries(LineSeries, innerOptions).setData(buildLevelData(data.candles || [], innerStart, innerS));
  }
};

const addAnnotations = (candleSeries, annotations) => {
  if (annotations.trigger_price) {
    candleSeries.createPriceLine({
      price: annotations.trigger_price,
      color: '#e3b341',
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
    markers.push({ time: annotations.trigger_date, position: 'belowBar', color: '#3fb950', shape: 'arrowUp', text: 'TRIG' });
  }
  const mfe20d = finiteNumber(annotations.mfe_20d);
  const mae20d = finiteNumber(annotations.mae_20d);
  if (annotations.mfe_20d_date && mfe20d != null) {
    markers.push({ time: annotations.mfe_20d_date, position: 'aboveBar', color: '#3fb950', shape: 'circle', text: `MFE ${(mfe20d * 100).toFixed(1)}%` });
  }
  if (annotations.mae_20d_date && mae20d != null) {
    markers.push({ time: annotations.mae_20d_date, position: 'belowBar', color: '#c76b73', shape: 'circle', text: `MAE ${(mae20d * 100).toFixed(1)}%` });
  }
  return markers;
};

const setFocusedRange = (chart, data, baseEnd) => {
  if (!data.candles?.length) return;
  const displayStart = Math.max(0, baseEnd - Math.max(data.base_len + 22, 42));
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
    barOptions: { upColor: '#d8dbe5', downColor: '#d8dbe5', thinBars: false },
    volumes: data?.volumes,
    showVolume: true,
    volumeScaleTop: 0.82,
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
      addStructureLevels(chart, data, baseEnd);
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
