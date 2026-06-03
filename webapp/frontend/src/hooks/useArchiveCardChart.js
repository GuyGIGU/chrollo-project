import { useEffect, useRef, useState } from 'react';
import { BarSeries, createChart, HistogramSeries, LineSeries } from 'lightweight-charts';

const MAX_VISIBLE_BARS = 72;

export default function useArchiveCardChart({ chartData, setup }) {
  const chartContainerRef = useRef(null);
  const [chartError, setChartError] = useState(false);

  useEffect(() => {
    const container = chartContainerRef.current;
    if (!container || !chartData?.candles) return undefined;

    container.innerHTML = '';
    setChartError(false);
    let disposed = false;
    let chart = null;

    try {
      chart = createMiniChart(container);
      drawCandles(chart, chartData);
      drawVolume(chart, chartData);
      drawStructureLines(chart, chartData);
      setVisibleStructureRange(chart, chartData);
    } catch (error) {
      console.error(`[ArchiveCard] Chart init failed for ${setup.ticker}:`, error);
      setChartError(true);
      return undefined;
    }

    const handleResize = () => {
      if (!disposed && container?.isConnected && chart) {
        try {
          chart.applyOptions({
            height: container.clientHeight,
            width: container.clientWidth,
          });
          setVisibleStructureRange(chart, chartData);
        } catch {
          // The chart can detach during tab changes.
        }
      }
    };
    window.addEventListener('resize', handleResize);
    const resizeTimeout = setTimeout(handleResize, 80);

    return () => {
      disposed = true;
      clearTimeout(resizeTimeout);
      window.removeEventListener('resize', handleResize);
      if (chart) {
        try {
          chart.remove();
        } catch {
          // Removing a detached chart is harmless.
        }
      }
      if (container) container.innerHTML = '';
    };
  }, [chartData, setup.id, setup.ticker]);

  return { chartContainerRef, chartError };
}

const createMiniChart = (container) => createChart(container, {
  crosshair: { mode: 0 },
  grid: {
    horzLines: { color: 'rgba(47, 52, 71, 0.13)' },
    vertLines: { color: 'rgba(47, 52, 71, 0.13)' },
  },
  handleScale: false,
  handleScroll: false,
  height: container.clientHeight || 220,
  layout: {
    background: { type: 'solid', color: '#141721' },
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 10,
    textColor: '#747c8f',
  },
  rightPriceScale: { borderColor: 'rgba(47, 52, 71, 0.56)', scaleMargins: { top: 0.08, bottom: 0.2 } },
  timeScale: { borderColor: 'rgba(47, 52, 71, 0.56)', fixLeftEdge: true, fixRightEdge: true, timeVisible: false },
  width: container.clientWidth || 340,
});

const drawCandles = (chart, chartData) => {
  const series = chart.addSeries(BarSeries, {
    downColor: '#d7dae4',
    lastValueVisible: false,
    priceLineVisible: false,
    thinBars: false,
    upColor: '#d7dae4',
  });
  series.setData(colorStructureCandles(chartData));
};

const drawVolume = (chart, chartData) => {
  const series = chart.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, priceScaleId: 'volume' });
  series.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
  series.setData(chartData.volumes);
};

const drawStructureLines = (chart, chartData) => {
  const baseEnd = getBaseEnd(chartData);
  const startIdx = Math.max(0, baseEnd - chartData.base_len + 1);
  const midValue = (chartData.R + chartData.S) / 2;
  const rData = [];
  const sData = [];
  const midData = [];

  for (let index = startIdx; index < chartData.candles.length; index += 1) {
    const time = chartData.candles[index].time;
    rData.push({ time, value: chartData.R });
    sData.push({ time, value: chartData.S });
    midData.push({ time, value: midValue });
  }

  addLine(chart, '#4488ff', 2).setData(rData);
  addLine(chart, '#4488ff', 2).setData(sData);
  addLine(chart, 'rgba(139, 148, 158, 0.4)', 1, 2).setData(midData);
};

const addLine = (chart, color, lineWidth, lineStyle) => chart.addSeries(LineSeries, {
  color,
  crosshairMarkerVisible: false,
  lastValueVisible: false,
  lineStyle,
  lineWidth,
  priceLineVisible: false,
});

const colorStructureCandles = (chartData) => {
  const candles = JSON.parse(JSON.stringify(chartData.candles));
  const baseEnd = getBaseEnd(chartData);
  if (chartData.base_len <= 0) return candles;

  colorBase(candles, chartData, baseEnd);
  colorLps(candles, chartData, baseEnd);
  return candles;
};

const colorBase = (candles, chartData, baseEnd) => {
  const baseStart = Math.max(0, baseEnd - chartData.base_len + 1);
  if (chartData.r_anchor == null || chartData.s_anchor == null) {
    paintRange(candles, baseStart, baseEnd, '#555555');
    return;
  }

  const rawBaseStart = baseEnd - chartData.base_len + 1;
  const rBar = rawBaseStart + chartData.r_anchor;
  const sBar = rawBaseStart + chartData.s_anchor;
  paintRange(candles, Math.min(rBar, sBar), Math.max(rBar, sBar), '#555555');
};

const colorLps = (candles, chartData, baseEnd) => {
  if (chartData.lps_len <= 0 || chartData.lps_offset === undefined) return;
  const lpsEnd = baseEnd - chartData.lps_offset;
  const lpsStart = Math.max(0, lpsEnd - chartData.lps_len + 1);
  paintRange(candles, lpsStart, lpsEnd, '#e3b341');
};

const paintRange = (candles, start, end, color) => {
  for (let index = start; index <= end; index += 1) {
    if (index >= 0 && index < candles.length) candles[index].color = color;
  }
};

const setVisibleStructureRange = (chart, chartData) => {
  if (chartData.candles.length === 0) {
    chart.timeScale().fitContent();
    return;
  }
  const baseEnd = getBaseEnd(chartData);
  const baseStart = Math.max(0, baseEnd - (chartData.base_len || 0) + 1);
  const forwardBars = chartData.forward_bars || 0;
  const leftPadding = Math.max(6, Math.min(10, Math.round((chartData.base_len || 0) * 0.28)));
  const rightPadding = Math.max(5, Math.min(9, forwardBars + 5));
  const rightEdge = Math.min(chartData.candles.length - 1, baseEnd + rightPadding);
  const leftEdge = Math.max(0, baseStart - leftPadding);

  chart.timeScale().setVisibleLogicalRange({
    from: Math.max(leftEdge, rightEdge - MAX_VISIBLE_BARS),
    to: rightEdge,
  });
};

const getBaseEnd = (chartData) => chartData.candles.length - 1 - (chartData.forward_bars || 0);
