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
  timeScale: { borderColor: '#2f3447', timeVisible: false, fixLeftEdge: false, fixRightEdge: false },
  handleScroll: true,
  handleScale: true,
});

export default function TimeframeMainChart({ candles, volumes, boxR, boxS, label, state }) {
  const containerRef = useRef(null);
  const [chartError, setChartError] = useState(false);

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
      const candleSeries = chart.addSeries(BarSeries, {
        upColor: '#26a69a',
        downColor: '#ef5350',
        lastValueVisible: false,
        priceLineVisible: false,
        thinBars: false,
      });
      candleSeries.setData(candles || []);

      if (volumes?.length) {
        const volumeSeries = chart.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, priceScaleId: 'tfvol' });
        volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
        volumeSeries.setData(volumes);
      }

      const cand = candles || [];
      const r = Number(boxR);
      const s = Number(boxS);
      if (cand.length && Number.isFinite(r) && Number.isFinite(s)) {
        const level = { color: '#2457b8', lineWidth: 2, crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false };
        chart.addSeries(LineSeries, level).setData(cand.map(k => ({ time: k.time, value: r })));
        chart.addSeries(LineSeries, level).setData(cand.map(k => ({ time: k.time, value: s })));
        chart.addSeries(LineSeries, {
          ...level,
          color: 'rgba(139, 148, 158, 0.40)',
          lineWidth: 1,
          lineStyle: 2,
        }).setData(cand.map(k => ({ time: k.time, value: (r + s) / 2 })));
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
  }, [candles, volumes, boxR, boxS]);

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
    <div style={{ height: '100%', position: 'relative' }}>
      <div ref={containerRef} style={{ height: '100%', position: 'relative' }} />
      {state ? (
        <div style={{
          alignItems: 'center',
          background: 'rgba(20, 23, 33, 0.74)',
          border: '1px solid var(--border-color)',
          borderRadius: 6,
          display: 'flex',
          gap: 8,
          left: 10,
          padding: '3px 9px',
          pointerEvents: 'none',
          position: 'absolute',
          top: 8,
          zIndex: 3,
        }}>
          <span style={{ color: 'var(--text-main)', fontSize: 11, fontWeight: 700, letterSpacing: 0.4 }}>{label}</span>
          <span style={{ color: state.trend.col, fontSize: 12, lineHeight: 1 }}>{state.trend.sym}</span>
          <span style={{ color: state.col, fontSize: 11, fontWeight: 600 }}>{state.text}</span>
          {state.nested ? (
            <span title="The daily base sits inside this higher-timeframe box (tight alignment)" style={{ color: '#ff9f43', fontSize: 10 }}>⊂ nested</span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
