import React, { useEffect, useRef, useState } from 'react';
import { createChart, BarSeries, LineSeries, HistogramSeries } from 'lightweight-charts';

const chartOptions = (width, height) => ({
  width,
  height,
  layout: {
    background: { type: 'solid', color: '#171922' },
    textColor: '#7f879a',
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 11,
  },
  grid: {
    vertLines: { color: 'rgba(47, 52, 71, 0.18)' },
    horzLines: { color: 'rgba(47, 52, 71, 0.18)' },
  },
  crosshair: { mode: 0 },
  rightPriceScale: { borderColor: '#2f3447', scaleMargins: { top: 0.08, bottom: 0.22 } },
  timeScale: {
    borderColor: '#2f3447',
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

  if (data.lps_len > 0 && data.lps_offset !== undefined) {
    const lpsEnd = baseEnd - data.lps_offset;
    const lpsStart = Math.max(0, lpsEnd - data.lps_len + 1);
    for (let index = lpsStart; index <= lpsEnd; index += 1) {
      if (index >= 0 && index < candles.length) candles[index].color = '#d4b85a';
    }
  }

  return candles;
};

const buildLevelData = (candles, startIndex, value) =>
  candles.slice(startIndex).map((candle) => ({ time: candle.time, value }));

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
  chart.timeScale().setVisibleLogicalRange({
    from: Math.max(0, baseStart - leftPadding),
    to: Math.min(candles.length - 1, baseEnd + rightPadding),
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
    let disposed = false;
    let chart = null;

    try {
      const width = container.clientWidth || 380;
      const height = container.clientHeight || 240;
      chart = createChart(container, chartOptions(width, height));

      const candles = colorCandles(data);
      const candleSeries = chart.addSeries(BarSeries, {
        upColor: '#d8dbe5',
        downColor: '#d8dbe5',
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
        color: '#5b8aff',
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

      if (Number.isFinite(Number(data.trigger))) {
        candleSeries.createPriceLine({
          price: Number(data.trigger),
          color: '#e3b341',
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: false,
          title: '',
        });
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

    const handleResize = () => {
      if (!disposed && container?.isConnected && chart) {
        try {
          chart.applyOptions({ width: container.clientWidth });
          focusSetupRange(chart, data);
        } catch {
          /* container detached */
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
