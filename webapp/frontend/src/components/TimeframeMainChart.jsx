import React, { useEffect, useRef, useState } from 'react';
import { createChart, BarSeries, LineSeries, HistogramSeries } from 'lightweight-charts';

// The big, interactive weekly/monthly chart behind the modal's D/W/M interval
// tabs. It's the SAME Trend+Box read the daily engine does, one and two
// timeframes up ("all relative and derivative"): candles are resampled on the
// backend (output/dashboard.py) from the full daily history; the blue rails are
// the higher-timeframe consolidation box when one is in view; the caption is the
// plain-language structural read. Styled to match the daily chart
// (useScreenerModalChart) so switching timeframes feels like one TradingView pane.

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
  rightPriceScale: { borderColor: '#2f3447', scaleMargins: { top: 0.08, bottom: 0.22 } },
  timeScale: { borderColor: '#2f3447', timeVisible: true, fixLeftEdge: false, fixRightEdge: false },
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

// null/'' -> null (NOT 0). Number(null) === 0, which would otherwise draw a
// phantom rail at price 0 for any timeframe with no box (the daily chart never
// hits this because a fired daily setup always has an R/S).
const finiteNumber = (value) => {
  if (value == null || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

const buildLevelData = (candles, value) =>
  candles.map(candle => ({ time: candle.time, value }));

// Colour the structure candles exactly like the daily chart: the base-limb
// swing (the bars that set the rails) grey, the right-side LPS span gold. Dates
// come from htf.chart_box; bars outside both spans keep the default bar colour.
const colorStructureCandles = (candles, { limbStart, limbEnd, lpsStart, lpsEnd }) => {
  const out = candles.map(candle => ({ ...candle }));
  const paint = (from, to, color) => {
    if (!from || !to) return;
    for (let i = 0; i < out.length; i += 1) {
      if (out[i].time >= from && out[i].time <= to) out[i].color = color;
    }
  };
  paint(limbStart, limbEnd, '#5d6474');   // base limb (root swing) — grey
  paint(lpsStart, lpsEnd, '#e3b341');      // LPS support test — gold
  return out;
};

export default function TimeframeMainChart({ candles, volumes, box, label }) {
  const containerRef = useRef(null);
  const [chartError, setChartError] = useState(false);
  const boxR = box?.r;
  const boxS = box?.s;
  const boxStart = box?.start_date;
  const limbStart = box?.limb_start_date;
  const limbEnd = box?.limb_end_date;
  const lpsStart = box?.lps_start_date;
  const lpsEnd = box?.lps_end_date;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    container.innerHTML = '';
    setChartError(false);
    let chart = null;
    let disposed = false;
    let handleResize = null;
    let resizeTimeout = null;

    try {
      chart = createChart(container, chartOptions(container.clientWidth || 600, container.clientHeight || 360));
      const candleSeries = chart.addSeries(BarSeries, { upColor: '#d8dbe5', downColor: '#d8dbe5', thinBars: false });
      candleSeries.setData(colorStructureCandles(candles || [], { limbStart, limbEnd, lpsStart, lpsEnd }));

      if (volumes?.length) {
        const volumeSeries = chart.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, priceScaleId: 'volume' });
        volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
        volumeSeries.setData(volumes);
      }

      const cand = candles || [];
      const r = finiteNumber(boxR);
      const s = finiteNumber(boxS);
      if (cand.length && r != null && s != null) {
        // Anchor the rails to the bars the box is born from (boxStart) — a
        // bounded line exactly like the daily chart, not a full-width rail.
        let from = 0;
        if (boxStart) {
          const found = cand.findIndex(candle => candle.time >= boxStart);
          from = found < 0 ? 0 : found;
        }
        const railBars = cand.slice(from);
        chart.addSeries(LineSeries, levelOptions).setData(buildLevelData(railBars, r));
        chart.addSeries(LineSeries, levelOptions).setData(buildLevelData(railBars, s));
        chart.addSeries(LineSeries, {
          ...levelOptions,
          color: 'rgba(139, 148, 158, 0.45)',
          lineWidth: 1,
          lineStyle: 2,
        }).setData(buildLevelData(railBars, (r + s) / 2));
      }

      chart.timeScale().fitContent();

      handleResize = () => {
        if (!disposed && container.isConnected) {
          chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
        }
      };
      window.addEventListener('resize', handleResize);
      resizeTimeout = setTimeout(handleResize, 100);
    } catch (err) {
      console.error('[TimeframeMainChart] init failed:', err);
      setChartError(true);
      return undefined;
    }

    return () => {
      disposed = true;
      if (resizeTimeout) clearTimeout(resizeTimeout);
      if (handleResize) window.removeEventListener('resize', handleResize);
      if (chart) {
        try {
          chart.remove();
        } catch {
          /* safe to ignore */
        }
      }
      if (container) container.innerHTML = '';
    };
  }, [candles, volumes, boxR, boxS, boxStart, limbStart, limbEnd, lpsStart, lpsEnd]);

  if (chartError) {
    return (
      <div style={{ alignItems: 'center', color: 'var(--text-muted)', display: 'flex', fontSize: 12, height: '100%', justifyContent: 'center' }}>
        Chart unavailable
      </div>
    );
  }

  if (!candles?.length) {
    return (
      <div style={{ alignItems: 'center', color: 'var(--text-faint)', display: 'flex', fontSize: 12, height: '100%', justifyContent: 'center' }}>
        No {label?.toLowerCase()} data yet (needs more history)
      </div>
    );
  }

  return (
    <div className="screener-modal-chart" style={{ height: '100%', minHeight: 0, position: 'relative' }}>
      <div ref={containerRef} style={{ height: '100%', position: 'relative' }} />
    </div>
  );
}
