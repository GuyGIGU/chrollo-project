import React, { useEffect, useRef, useState } from 'react';
import { createChart, BarSeries, LineSeries, HistogramSeries } from 'lightweight-charts';

const MAX_VISIBLE_BARS = 72;

const chartOptions = (width, height) => ({
  width,
  height,
  // ResizeObserver-backed: keeps the chart matched to the card's real width so
  // the right price scale can't overflow and get clipped when the responsive
  // grid sizes cards differently across monitors.
  autoSize: true,
  layout: {
    background: { type: 'solid', color: '#141721' },
    textColor: '#747c8f',
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 10,
  },
  grid: {
    vertLines: { color: 'rgba(47, 52, 71, 0.13)' },
    horzLines: { color: 'rgba(47, 52, 71, 0.13)' },
  },
  crosshair: { mode: 0 },
  rightPriceScale: { borderColor: 'rgba(47, 52, 71, 0.56)', scaleMargins: { top: 0.08, bottom: 0.2 } },
  timeScale: {
    borderColor: 'rgba(47, 52, 71, 0.56)',
    timeVisible: false,
    fixLeftEdge: true,
    fixRightEdge: true,
  },
  handleScroll: false,
  handleScale: false,
});

const colorCandles = (data) => {
  const candles = JSON.parse(JSON.stringify(data.candles || []));
  if (data.base_len <= 0) return candles;

  const forwardBars = data.forward_bars || 0;
  const baseEnd = candles.length - 1 - forwardBars;
  const baseStart = baseEnd - data.base_len + 1;
  const limbStart = Math.min(baseStart + data.r_anchor, baseStart + data.s_anchor);
  const limbEnd = Math.max(baseStart + data.r_anchor, baseStart + data.s_anchor);
  for (let index = limbStart; index <= limbEnd; index += 1) {
    if (index >= 0 && index < candles.length) candles[index].color = '#596070';
  }

  for (const test of data.lps_tests || []) {
    const start = indexOnOrAfter(candles, test.start_date);
    const end = indexOnOrAfter(candles, test.end_date);
    if (start == null || end == null) continue;
    for (let index = start; index <= end; index += 1) {
      if (index >= 0 && index < candles.length) candles[index].color = '#d4b85a';
    }
  }

  if (data.lps_len > 0 && data.lps_offset !== undefined) {
    const lpsEnd = baseEnd - data.lps_offset;
    const lpsStart = Math.max(0, lpsEnd - data.lps_len + 1);
    for (let index = lpsStart; index <= lpsEnd; index += 1) {
      if (index >= 0 && index < candles.length) candles[index].color = '#d4b85a';
    }
  }

  return candles;
};

const candleDate = (candle) => {
  if (!candle?.time) return '';
  if (typeof candle.time === 'string') return candle.time.slice(0, 10);
  if (typeof candle.time === 'object') {
    const month = String(candle.time.month).padStart(2, '0');
    const day = String(candle.time.day).padStart(2, '0');
    return `${candle.time.year}-${month}-${day}`;
  }
  return '';
};

const indexOnOrAfter = (candles, rawDate) => {
  const target = typeof rawDate === 'string' ? rawDate.slice(0, 10) : null;
  if (!target) return null;
  const index = candles.findIndex(candle => candleDate(candle) >= target);
  return index >= 0 ? index : null;
};

const buildLevelData = (candles, startIndex, value) =>
  candles.slice(startIndex).map((candle) => ({ time: candle.time, value }));

const finiteNumber = (value) => {
  if (value == null || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

const setupIndexes = (data) => {
  const candles = data.candles || [];
  const forwardBars = data.forward_bars || 0;
  const baseEnd = Math.max(0, candles.length - 1 - forwardBars);
  const baseStart = Math.max(0, baseEnd - data.base_len + 1);
  return { baseEnd, baseStart, candles, forwardBars };
};

const focusSetupRange = (chart, data) => {
  const { baseEnd, baseStart, candles, forwardBars } = setupIndexes(data);
  if (!candles.length) return;

  const leftPadding = Math.max(6, Math.min(10, Math.round(data.base_len * 0.28)));
  const rightPadding = Math.max(5, Math.min(9, forwardBars + 5));
  const rightEdge = Math.min(candles.length - 1, baseEnd + rightPadding);
  const leftEdge = Math.max(0, baseStart - leftPadding);

  chart.timeScale().setVisibleLogicalRange({
    from: Math.max(leftEdge, rightEdge - MAX_VISIBLE_BARS),
    to: rightEdge,
  });
};

const ScreenerMiniChart = ({ ticker, data }) => {
  const containerRef = useRef(null);
  const [chartError, setChartError] = useState(false);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    container.innerHTML = '';
    setChartError(false);
    let chart = null;

    try {
      const width = container.clientWidth || 380;
      const height = container.clientHeight || 240;
      chart = createChart(container, chartOptions(width, height));

      const candles = colorCandles(data);
      const candleSeries = chart.addSeries(BarSeries, {
        upColor: '#d7dae4',
        downColor: '#d7dae4',
        lastValueVisible: false,
        priceLineVisible: false,
        thinBars: false,
      });
      candleSeries.setData(candles);

      const volumeSeries = chart.addSeries(HistogramSeries, {
        priceFormat: { type: 'volume' },
        priceScaleId: 'volume',
      });
      volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
      volumeSeries.setData(data.volumes || []);

      const levelOptions = {
        color: '#2457b8',
        lineWidth: 2,
        crosshairMarkerVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
      };
      const rSeries = chart.addSeries(LineSeries, levelOptions);
      const sSeries = chart.addSeries(LineSeries, levelOptions);
      const midSeries = chart.addSeries(LineSeries, {
        ...levelOptions,
        color: 'rgba(154, 161, 178, 0.42)',
        lineWidth: 1,
        lineStyle: 2,
      });

      const { baseStart } = setupIndexes(data);
      const midValue = (data.R + data.S) / 2;
      rSeries.setData(buildLevelData(data.candles || [], baseStart, data.R));
      sSeries.setData(buildLevelData(data.candles || [], baseStart, data.S));
      midSeries.setData(buildLevelData(data.candles || [], baseStart, midValue));

      const innerR = finiteNumber(data.inner_R);
      const innerS = finiteNumber(data.inner_S);
      const innerStartBar = finiteNumber(data.inner_start_bar);
      if (innerR != null && innerS != null && innerStartBar != null) {
        const innerStart = Math.max(0, Math.min(candles.length - 1, Math.trunc(innerStartBar)));
        const innerOptions = {
          ...levelOptions,
          color: '#5f8fe6',
          lineWidth: 2,
        };
        chart.addSeries(LineSeries, innerOptions).setData(buildLevelData(data.candles || [], innerStart, innerR));
        chart.addSeries(LineSeries, innerOptions).setData(buildLevelData(data.candles || [], innerStart, innerS));
      }

      if (data.base_len > 0 && data.candles?.length > 0) {
        focusSetupRange(chart, data);
      } else {
        chart.timeScale().fitContent();
      }
    } catch (err) {
      console.error(`[ScreenerMiniChart] Chart init failed for ${ticker}:`, err);
      setChartError(true);
      return undefined;
    }

    return () => {
      if (chart) {
        try {
          chart.remove();
        } catch {
          /* safe to ignore */
        }
      }
      if (container) container.innerHTML = '';
    };
  }, [ticker, data]);

  if (chartError) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '11px' }}>
        Chart failed to load
      </div>
    );
  }

  return <div ref={containerRef} style={{ flex: 1, minHeight: 0, position: 'relative', pointerEvents: 'none' }} />;
};

export default ScreenerMiniChart;
